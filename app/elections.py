"""Election lifecycle: create, read, vote, close, tally.

Wires together storage, anonymity, ballot types, and the faculty registry.
Does NOT know about HTTP — that's main.py's job.
"""
from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field

from .anonymity import new_ballot_id, new_election_salt, voter_receipt
from .ballots import approval, ranked, yes_no
from .election_templates import TEMPLATES, apply_candidate_filter
from .faculty import get_registry
from .storage import Storage, get_storage


class AlreadyVoted(Exception):
    pass


class ElectionClosed(Exception):
    pass


class ElectionNotFound(Exception):
    pass


class NotEligible(Exception):
    pass


class NotPermitted(Exception):
    pass


@dataclass
class Election:
    id: str
    title: str
    description: str
    template_id: str
    ballot_type: str          # "yes_no" | "approval" | "ranked"
    seats: int
    max_ranks: int
    candidate_oids: list[str]  # faculty IDs on the ballot
    excluded_oids: list[str]   # faculty excluded from voting (sabbatical, recusal)
    quorum_fraction: float
    require_quorum: bool
    eligible_count: int        # snapshot at creation time (full faculty - excluded)
    created_at: float
    created_by_oid: str
    status: str                # "open" | "closed"
    salt: str                  # per-election HMAC salt, never shown to voters
    parent_election_id: str = ""  # if spawned from a prior election
    extra_candidates: list[dict] = field(default_factory=list)
    # Each extra: {"id": "ext_xxx", "name": "...", "rank": "...", "photo": "filename.jpg" | None}
    closes_at: float = 0.0  # Unix timestamp; 0 means no scheduled close.

    def to_public(self) -> dict:
        d = self.to_storage()
        d.pop("salt", None)
        return d

    def to_storage(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "template_id": self.template_id,
            "ballot_type": self.ballot_type,
            "seats": self.seats,
            "max_ranks": self.max_ranks,
            "candidate_oids": list(self.candidate_oids),
            "excluded_oids": list(self.excluded_oids),
            "quorum_fraction": self.quorum_fraction,
            "require_quorum": self.require_quorum,
            "eligible_count": self.eligible_count,
            "created_at": self.created_at,
            "created_by_oid": self.created_by_oid,
            "status": self.status,
            "salt": self.salt,
            "parent_election_id": self.parent_election_id,
            "extra_candidates": list(self.extra_candidates),
            "closes_at": self.closes_at,
        }

    @classmethod
    def from_storage(cls, d: dict) -> "Election":
        d = dict(d)
        d.setdefault("extra_candidates", [])
        d.setdefault("parent_election_id", "")
        d.setdefault("closes_at", 0.0)
        return cls(**d)


def create_election(
    *,
    title: str,
    description: str,
    template_id: str,
    created_by_oid: str,
    candidate_oids: list[str] | None = None,
    excluded_oids: list[str] | None = None,
    seats: int | None = None,
    max_ranks: int | None = None,
    require_quorum: bool | None = None,
    parent_election_id: str = "",
    extra_candidates: list[dict] | None = None,
    election_id: str | None = None,
    closes_at: float = 0.0,
    storage: Storage | None = None,
) -> Election:
    if template_id not in TEMPLATES:
        raise ValueError(f"unknown template: {template_id}")
    t = TEMPLATES[template_id]
    s = storage or get_storage()
    reg = get_registry()

    if candidate_oids is None:
        candidate_oids = apply_candidate_filter(t.candidate_filter)
    # Drop any candidate that's been excluded.
    excluded = list(excluded_oids or [])
    candidate_oids = [c for c in candidate_oids if c not in set(excluded)]

    # Append extra (ad-hoc) candidates to the candidate pool.
    extras = list(extra_candidates or [])
    for ex in extras:
        if ex["id"] not in candidate_oids:
            candidate_oids.append(ex["id"])

    eligible = [m.id for m in reg.members if m.id not in set(excluded)]

    election = Election(
        id=election_id or secrets.token_urlsafe(8),
        title=title,
        description=description,
        template_id=template_id,
        ballot_type=t.ballot_type,
        seats=seats if seats is not None else t.seats,
        max_ranks=max_ranks if max_ranks is not None else t.max_ranks,
        candidate_oids=candidate_oids,
        excluded_oids=excluded,
        quorum_fraction=t.quorum_fraction,
        require_quorum=require_quorum if require_quorum is not None else t.require_quorum,
        eligible_count=len(eligible),
        created_at=time.time(),
        created_by_oid=created_by_oid,
        status="open",
        salt=new_election_salt(),
        parent_election_id=parent_election_id,
        extra_candidates=extras,
        closes_at=closes_at,
    )
    s.put_election(election.id, election.to_storage())
    return election


def get_election(election_id: str, storage: Storage | None = None) -> Election:
    s = storage or get_storage()
    data = s.get_election(election_id)
    if data is None:
        raise ElectionNotFound(election_id)
    election = Election.from_storage(data)
    # Lazy auto-close: if a close time was set and is in the past, transition.
    if (
        election.status == "open"
        and election.closes_at
        and time.time() >= election.closes_at
    ):
        election.status = "closed"
        s.put_election(election.id, election.to_storage())
    return election


def list_elections(storage: Storage | None = None) -> list[Election]:
    s = storage or get_storage()
    now = time.time()
    out: list[Election] = []
    for d in s.list_elections():
        e = Election.from_storage(d)
        if e.status == "open" and e.closes_at and now >= e.closes_at:
            e.status = "closed"
            s.put_election(e.id, e.to_storage())
        out.append(e)
    return out


def cast_vote(
    election_id: str,
    voter_oid: str,
    ballot_input: dict,
    storage: Storage | None = None,
) -> str:
    """Record one vote. `ballot_input` shape depends on the ballot type:
      yes_no:   {"choice": "yes"|"no"|"abstain"}
      approval: {"approved": [faculty_id, ...]}
      ranked:   {"ranking":  [faculty_id, ...]}

    Returns the (random) ballot ID.
    """
    s = storage or get_storage()
    election = get_election(election_id, s)
    if election.status != "open":
        raise ElectionClosed(election_id)

    if voter_oid in set(election.excluded_oids):
        raise NotEligible(voter_oid)

    receipt = voter_receipt(voter_oid, election.salt)
    if s.has_voted(election.id, receipt):
        raise AlreadyVoted(election_id)

    if election.ballot_type == "yes_no":
        ballot = yes_no.serialize(ballot_input["choice"])
    elif election.ballot_type == "approval":
        ballot = approval.serialize(
            list(ballot_input.get("approved", [])),
            set(election.candidate_oids),
        )
    elif election.ballot_type == "ranked":
        ballot = ranked.serialize(
            list(ballot_input.get("ranking", [])),
            set(election.candidate_oids),
            election.max_ranks,
        )
    else:
        raise ValueError(f"unsupported ballot type: {election.ballot_type}")

    ballot_id = new_ballot_id()
    # Write ballot first, then voter receipt. If receipt write fails the
    # voter may retry; orphan ballots don't matter because the tally
    # operates on stored ballots only (receipts gate participation, not
    # counting). See threat_model.md.
    s.put_ballot(election.id, ballot_id, ballot)
    s.mark_voted(election.id, receipt)
    return ballot_id


def delete_election(
    election_id: str,
    deleted_by_oid: str,
    storage: Storage | None = None,
) -> None:
    """Permanently remove the election and all its data. Creator only."""
    s = storage or get_storage()
    election = get_election(election_id, s)
    if election.created_by_oid and deleted_by_oid != election.created_by_oid:
        raise NotPermitted("only the creator can delete this election")
    s.delete_election(election.id)


def close_election(
    election_id: str,
    closed_by_oid: str,
    storage: Storage | None = None,
) -> Election:
    s = storage or get_storage()
    election = get_election(election_id, s)
    if election.created_by_oid and closed_by_oid != election.created_by_oid:
        raise NotPermitted("only the creator can close this election")
    election.status = "closed"
    s.put_election(election.id, election.to_storage())
    return election


def tally(election_id: str, storage: Storage | None = None) -> dict:
    s = storage or get_storage()
    election = get_election(election_id, s)
    ballots = list(s.iter_ballots(election.id))

    if election.ballot_type == "yes_no":
        result = yes_no.tally(ballots)
    elif election.ballot_type == "approval":
        result = approval.tally(ballots, election.candidate_oids)
    elif election.ballot_type == "ranked":
        result = ranked.tally(
            ballots,
            election.candidate_oids,
            seats=election.seats,
            election_id=election.id,
        )
    else:
        raise ValueError(f"unsupported ballot type: {election.ballot_type}")

    # Annotate with quorum info.
    total = result.get("total_cast", 0)
    needed = int(election.eligible_count * election.quorum_fraction + 0.999) \
        if election.eligible_count else 0
    result["eligible_count"] = election.eligible_count
    result["quorum_fraction"] = election.quorum_fraction
    result["quorum_required"] = election.require_quorum
    result["quorum_needed"] = needed
    result["quorum_met"] = total >= needed
    return result
