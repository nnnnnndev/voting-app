import json
import secrets
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from starlette.datastructures import UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import app_config, elections, vote_assets
from .anonymity import voter_receipt
from .auth import current_voter, router as auth_router
from .config import settings
from .election_templates import TEMPLATES, apply_candidate_filter
from .faculty import get_registry
from .storage import get_storage

APP_DIR = Path(__file__).resolve().parent
PHOTOS_DIR = APP_DIR.parent / "faculty photos"

app = FastAPI(title="MIE Voting App")
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)
app.include_router(auth_router)
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
app.mount("/photos", StaticFiles(directory=PHOTOS_DIR), name="photos")

# Per-vote uploaded photos for ad-hoc candidates.
vote_assets.ASSETS_ROOT.mkdir(parents=True, exist_ok=True)
app.mount(
    "/vote-photos",
    StaticFiles(directory=vote_assets.ASSETS_ROOT),
    name="vote-photos",
)

templates = Jinja2Templates(directory=APP_DIR / "templates")


@app.on_event("startup")
def _startup() -> None:
    get_registry()


def _require_voter(request: Request) -> dict:
    voter = current_voter(request)
    if not voter:
        raise HTTPException(401, "Sign in first")
    return voter


def _ctx(request: Request, **extra) -> dict:
    return {
        "request": request,
        "voter": current_voter(request),
        "branding": app_config.load().branding,
        **extra,
    }


def _initials(name: str) -> str:
    parts = [p for p in name.split() if p and p[0].isalpha()]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][0].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _build_cards(e: elections.Election) -> list[dict]:
    """One uniform card dict per candidate, merging faculty and extras.
    Each card carries eligibility info and recent-history strings drawn
    from the faculty status sheet (if loaded)."""
    reg = get_registry()
    extras_by_id = {c["id"]: c for c in e.extra_candidates}
    ay = reg.active_ay  # used for greying out DPC candidates
    cards = []
    for cid in e.candidate_oids:
        if cid in reg.by_id:
            m = reg.by_id[cid]
            eligible, reason = reg.eligibility(m.id, ay)
            history = [s.display for s in reg.recent_statuses(m.id, n=4)]
            cards.append({
                "id": m.id, "name": m.name, "rank": m.rank,
                "initials": m.initials,
                "photo_url": f"/photos/{m.photo}" if m.photo else None,
                "eligible": eligible,
                "ineligible_reason": reason,
                "history": history,
            })
        elif cid in extras_by_id:
            ex = extras_by_id[cid]
            photo = ex.get("photo")
            cards.append({
                "id": ex["id"], "name": ex["name"],
                "rank": ex.get("rank", ""),
                "initials": _initials(ex["name"]),
                "photo_url": f"/vote-photos/{e.id}/{photo}" if photo else None,
                "eligible": True,
                "ineligible_reason": "",
                "history": [],
            })
    return cards


def _eligible_ids(cards: list[dict]) -> set[str]:
    return {c["id"] for c in cards if c["eligible"]}


def _cards_by_id(cards: list[dict]) -> dict[str, dict]:
    return {c["id"]: c for c in cards}


def _display_card(m, is_chair: bool = False) -> dict:
    """Build a non-interactive card dict for displaying a faculty member
    (no eligibility logic, no history toggle)."""
    return {
        "id": m.id, "name": m.name, "rank": m.rank,
        "initials": m.initials,
        "photo_url": f"/photos/{m.photo}" if m.photo else None,
        "eligible": True, "ineligible_reason": "", "history": [],
        "is_chair": is_chair,
    }


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    reg = get_registry()
    dpc = reg.current_dpc()
    chair_id = dpc["chair_id"]
    dpc_cards = {
        "served": [_display_card(m, is_chair=(m.id == chair_id)) for m in dpc["served"]],
        "alternate": [_display_card(m) for m in dpc["alternate"]],
        "non_voting": [_display_card(m) for m in dpc["non_voting"]],
    }
    all_e = elections.list_elections()
    all_e.sort(key=lambda e: e.created_at, reverse=True)
    return templates.TemplateResponse(
        request,
        "index.html",
        _ctx(
            request,
            open_elections=[e for e in all_e if e.status == "open"],
            closed_elections=[e for e in all_e if e.status == "closed"],
            dpc_cards=dpc_cards,
            active_ay=reg.active_ay,
        ),
    )


@app.get("/elections/new", response_class=HTMLResponse)
def new_election_form(request: Request, spawn_from: str = ""):
    _require_voter(request)
    reg = get_registry()
    parent = None
    inherited_candidate_ids: list[str] = []
    default_template = "general_motion"
    if spawn_from:
        try:
            parent = elections.get_election(spawn_from)
        except elections.ElectionNotFound:
            raise HTTPException(404, "Parent vote not found")
        if parent.status != "closed":
            raise HTTPException(400, "Parent vote must be closed first")
        t = elections.tally(parent.id)
        inherited_candidate_ids = [
            row["id"] for row in t.get("ranked", []) if row.get("approvals", 0) > 0
        ]
        if parent.template_id == "dpc_nomination_tenured":
            default_template = "dpc_composition_tenured"
        elif parent.template_id == "dpc_nomination_untenured":
            default_template = "dpc_composition_untenured"
        else:
            default_template = "custom_ranked"

    return templates.TemplateResponse(
        request,
        "new_election.html",
        _ctx(
            request,
            templates=list(TEMPLATES.values()),
            default_template=default_template,
            all_faculty=reg.members,
            parent=parent,
            inherited_candidate_ids=inherited_candidate_ids,
        ),
    )


@app.post("/elections/new")
async def new_election_submit(request: Request):
    voter = _require_voter(request)
    form = await request.form()
    template_id = form.get("template_id", "")
    title = (form.get("title") or "").strip()
    description = (form.get("description") or "").strip()
    excluded = form.getlist("excluded_oids")
    parent_id = form.get("parent_election_id", "") or ""

    if template_id not in TEMPLATES:
        raise HTTPException(400, f"Unknown template: {template_id}")
    if not title:
        raise HTTPException(400, "Title required")

    is_custom = template_id in ("custom_ranked", "custom_approval")

    # Pre-generate the vote id so we can save uploaded photos under it.
    vote_id = secrets.token_urlsafe(8)

    # Determine candidate pool.
    candidate_oids: list[str] | None = None
    if parent_id:
        # Spawn flow — pool comes from a hidden field.
        csv = form.get("candidate_oids", "") or ""
        candidate_oids = [c for c in csv.split(",") if c]
    elif is_custom:
        # Custom flow — multi-select on faculty.
        candidate_oids = form.getlist("faculty_candidate_oids")

    # Ad-hoc extras (custom flow only). Iterate up to 20 indexed slots.
    extras: list[dict] = []
    if is_custom:
        for i in range(20):
            name = (form.get(f"extra_name_{i}") or "").strip()
            if not name:
                continue
            rank = (form.get(f"extra_rank_{i}") or "").strip()
            ext_id = f"ext_{secrets.token_urlsafe(4)}"
            photo_filename: str | None = None
            upload = form.get(f"extra_photo_{i}")
            if isinstance(upload, UploadFile) and upload.filename:
                data = await upload.read()
                if data:
                    try:
                        photo_filename = vote_assets.save_photo(
                            vote_id, ext_id, upload.filename, data
                        )
                    except ValueError as ex:
                        raise HTTPException(400, f"Photo for '{name}': {ex}")
            extras.append({
                "id": ext_id,
                "name": name,
                "rank": rank,
                "photo": photo_filename,
            })

    try:
        e = elections.create_election(
            title=title,
            description=description,
            template_id=template_id,
            created_by_oid=voter["oid"],
            candidate_oids=candidate_oids,
            excluded_oids=list(excluded),
            parent_election_id=parent_id,
            extra_candidates=extras,
            election_id=vote_id,
        )
    except ValueError as ex:
        raise HTTPException(400, str(ex))
    return RedirectResponse(f"/elections/{e.id}", status_code=303)


@app.get("/elections/{election_id}", response_class=HTMLResponse)
def view_election(request: Request, election_id: str, voted: int = 0):
    voter = current_voter(request)
    try:
        e = elections.get_election(election_id)
    except elections.ElectionNotFound:
        raise HTTPException(404, "Vote not found")

    cards = _build_cards(e)
    cards_by_id = _cards_by_id(cards)

    already_voted = False
    if voter and e.status == "open":
        already_voted = get_storage().has_voted(
            e.id, voter_receipt(voter["oid"], e.salt)
        )

    tally_data = elections.tally(e.id) if e.status == "closed" else None
    is_creator = bool(voter and voter["oid"] == e.created_by_oid)

    # Has at least one extra-candidate photo on disk?
    has_extra_photos = vote_assets.vote_dir(e.id).exists() and any(
        vote_assets.vote_dir(e.id).iterdir()
    )

    return templates.TemplateResponse(
        request,
        "election.html",
        _ctx(
            request,
            election=e,
            candidates=cards,
            cards_by_id=cards_by_id,
            tally=tally_data,
            tally_json=json.dumps(tally_data, indent=2) if tally_data else "",
            already_voted=already_voted,
            is_creator=is_creator,
            just_voted=bool(voted),
            has_extra_photos=has_extra_photos,
            error=None,
        ),
    )


@app.post("/elections/{election_id}/vote")
async def cast_vote(request: Request, election_id: str):
    voter = _require_voter(request)
    form = await request.form()
    try:
        e = elections.get_election(election_id)
    except elections.ElectionNotFound:
        raise HTTPException(404, "Vote not found")

    if e.ballot_type == "yes_no":
        ballot_input = {"choice": form.get("choice", "")}
    elif e.ballot_type == "approval":
        approved_csv = form.get("approved", "") or ""
        ballot_input = {"approved": [c for c in approved_csv.split(",") if c]}
    elif e.ballot_type == "ranked":
        ranking_csv = form.get("ranking", "") or ""
        ballot_input = {"ranking": [c for c in ranking_csv.split(",") if c]}
    else:
        raise HTTPException(400, "unknown ballot type")

    # Drop selections of ineligible candidates (defense in depth; the UI
    # disables clicking them, but a forged form could still send them).
    eligible = _eligible_ids(_build_cards(e))
    if e.ballot_type == "approval":
        ballot_input["approved"] = [c for c in ballot_input["approved"] if c in eligible]
    elif e.ballot_type == "ranked":
        ballot_input["ranking"] = [c for c in ballot_input["ranking"] if c in eligible]

    try:
        elections.cast_vote(election_id, voter["oid"], ballot_input)
    except elections.AlreadyVoted:
        raise HTTPException(409, "You have already voted in this vote.")
    except elections.ElectionClosed:
        raise HTTPException(409, "This vote is closed.")
    except elections.NotEligible:
        raise HTTPException(403, "You are excluded from this vote.")
    except ValueError as ex:
        raise HTTPException(400, str(ex))
    return RedirectResponse(f"/elections/{election_id}?voted=1", status_code=303)


@app.post("/elections/{election_id}/close")
def close_election(request: Request, election_id: str):
    voter = _require_voter(request)
    try:
        elections.close_election(election_id, voter["oid"])
    except elections.NotPermitted as ex:
        raise HTTPException(403, str(ex))
    except elections.ElectionNotFound:
        raise HTTPException(404, "Vote not found")
    return RedirectResponse(f"/elections/{election_id}", status_code=303)


@app.post("/elections/{election_id}/purge-photos")
def purge_photos(request: Request, election_id: str):
    voter = _require_voter(request)
    try:
        e = elections.get_election(election_id)
    except elections.ElectionNotFound:
        raise HTTPException(404, "Vote not found")
    if e.created_by_oid != voter["oid"]:
        raise HTTPException(403, "Only the creator can purge photos.")
    vote_assets.purge_photos(e.id)
    # Clear photo fields on extras so they render as initials bubbles.
    for ex in e.extra_candidates:
        ex["photo"] = None
    get_storage().put_election(e.id, e.to_storage())
    return RedirectResponse(f"/elections/{e.id}", status_code=303)


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}
