"""Faculty registry.

Loads `faculty list.csv` at startup, fuzzy-matches faculty to photos in
`faculty photos/`, and exposes a stable in-memory list used throughout the
app for ballot candidates and (eventually) voter eligibility.

Faculty IDs are slugified names ("stephen_s_nonnenmann"), stable across
restarts. We'll later map these to Entra OIDs once we have real sign-ins.

Photos are matched by token overlap: any photo basename containing a
faculty member's last-name token (or first+last) is a candidate; we pick
the one with the most matching tokens. Unmatched faculty fall back to an
initials bubble in the UI.
"""
from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

CSV_PATH = Path(__file__).resolve().parent.parent / "faculty list.csv"
PHOTOS_DIR = Path(__file__).resolve().parent.parent / "faculty photos"

RANK_TENURED = {"Professor", "Associate Professor"}
RANK_UNTENURED = {"Assistant Professor"}
RANK_NON_FACULTY = {"Lecturer", "Senior Lecturer"}


@dataclass
class Faculty:
    id: str
    name: str
    rank: str
    photo: str | None = None  # filename within PHOTOS_DIR, or None
    untenured_override: bool | None = None  # set from status sheet
    statuses: list = field(default_factory=list)  # list[StatusEntry] from status sheet

    @property
    def initials(self) -> str:
        parts = [p for p in self.name.split() if p and p[0].isalpha()]
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][0].upper()
        return (parts[0][0] + parts[-1][0]).upper()

    @property
    def is_tenured(self) -> bool:
        # The status-sheet override only flips a faculty member to
        # untenured; otherwise we fall back to rank.
        if self.untenured_override is True:
            return False
        return self.rank in RANK_TENURED

    @property
    def is_untenured(self) -> bool:
        if self.untenured_override is True:
            return True
        return self.rank in RANK_UNTENURED

    @property
    def is_tenure_track(self) -> bool:
        return self.is_tenured or self.is_untenured


def _slugify(name: str) -> str:
    n = unicodedata.normalize("NFKD", name)
    n = n.encode("ascii", "ignore").decode("ascii")
    n = re.sub(r"[^a-zA-Z0-9]+", "_", n).strip("_").lower()
    return n


def _ascii_lower(s: str) -> str:
    n = unicodedata.normalize("NFKD", s)
    return n.encode("ascii", "ignore").decode("ascii").lower()


def _tokens(s: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", _ascii_lower(s)) if len(t) >= 2]


def _name_parts(name: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", _ascii_lower(name)) if t]


def _score(faculty_name: str, photo_stem: str) -> int:
    """Score how strongly a photo filename matches a faculty name.

    Exact token matches dominate substring matches by ~10x so that e.g.
    "chaitra.jpg" matches Chaitra Gopalappa (first-name exact, 30) and not
    Yossi Chait (last-name substring, 10).
    """
    parts = _name_parts(faculty_name)
    if not parts:
        return 0
    last = parts[-1]
    first = parts[0]
    middles = set(parts[1:-1])
    score = 0
    for pt in _tokens(photo_stem):
        if pt == last:
            score += 100
        elif len(last) >= 5 and (last in pt or pt in last):
            score += 10
        elif pt == first:
            score += 30
        elif len(first) >= 5 and (first in pt or pt in first):
            score += 5
        elif pt in middles:
            score += 5
    return score


def _match_photos(members: list["Faculty"], photo_files: list[Path]) -> None:
    """Assign at most one photo per faculty member, greedy by best score.

    Each photo can be claimed at most once. Highest-scoring (faculty, photo)
    pair wins; ties broken by faculty CSV order.
    """
    pairs: list[tuple[int, int, str]] = []  # (score, member_idx, photo_name)
    for i, m in enumerate(members):
        for p in photo_files:
            s = _score(m.name, p.stem)
            if s > 0:
                pairs.append((s, i, p.name))
    pairs.sort(key=lambda x: (-x[0], x[1], x[2]))
    used_member: set[int] = set()
    used_photo: set[str] = set()
    for score, i, photo in pairs:
        if i in used_member or photo in used_photo:
            continue
        members[i].photo = photo
        used_member.add(i)
        used_photo.add(photo)


@dataclass
class FacultyRegistry:
    members: list[Faculty] = field(default_factory=list)
    by_id: dict[str, Faculty] = field(default_factory=dict)
    _status_sheet: object = None  # set by _apply_status_sheet

    @property
    def active_ay(self) -> str:
        if self._status_sheet is None:
            return ""
        return self._status_sheet.active_ay

    def eligibility(self, faculty_id: str, ay: str = "") -> tuple[bool, str]:
        """Returns (eligible, reason). reason is empty when eligible."""
        if self._status_sheet is None or not ay:
            return True, ""
        m = self.by_id.get(faculty_id)
        if m is None:
            return True, ""
        excluded, reason = self._status_sheet.is_hard_excluded(m.name, ay)
        if excluded:
            return False, reason
        return True, ""

    def recent_statuses(self, faculty_id: str, n: int = 4) -> list:
        if self._status_sheet is None:
            return []
        m = self.by_id.get(faculty_id)
        if m is None:
            return []
        return self._status_sheet.recent_statuses(m.name, n=n)

    def current_dpc(self) -> dict:
        """Return the committee composition for the active AY:
        {
          'served': [Faculty, ...]    (includes the chair),
          'alternate': [Faculty, ...],
          'non_voting': [...],
          'chair_id': str | None      (faculty id of the chair if known),
        }.
        Empty if no status sheet is loaded.
        """
        result = {"served": [], "alternate": [], "non_voting": [], "chair_id": None}
        if self._status_sheet is None or not self.active_ay:
            return result
        ay = self.active_ay
        for m in self.members:
            for entry in m.statuses:
                if entry.ay != ay:
                    continue
                if entry.code in ("SERVED", "CHAIR"):
                    result["served"].append(m)
                    if entry.code == "CHAIR":
                        result["chair_id"] = m.id
                elif entry.code == "ALTERNATE":
                    result["alternate"].append(m)
                elif entry.code == "NON_VOTING":
                    result["non_voting"].append(m)
        return result

    @classmethod
    def load(
        cls,
        csv_path: Path = CSV_PATH,
        photos_dir: Path = PHOTOS_DIR,
        verbose: bool = False,
    ) -> "FacultyRegistry":
        photo_files = (
            [p for p in photos_dir.iterdir() if p.is_file()]
            if photos_dir.exists()
            else []
        )
        reg = cls()
        with csv_path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            assert header and header[0].strip().lower() == "name"
            for row in reader:
                if not row or not row[0].strip():
                    continue
                name = row[0].strip()
                rank = row[1].strip() if len(row) > 1 else ""
                fac = Faculty(id=_slugify(name), name=name, rank=rank)
                reg.members.append(fac)
                reg.by_id[fac.id] = fac
        _match_photos(reg.members, photo_files)
        reg._apply_status_sheet(verbose=verbose)
        if verbose:
            reg.print_photo_match_table()
        return reg

    def _apply_status_sheet(self, verbose: bool = False) -> None:
        """Load faculty_status.xlsx if present and apply tenure overrides
        and per-AY statuses."""
        from .faculty_status import get_sheet, reset_cache

        reset_cache()
        known = {m.name for m in self.members}
        sheet = get_sheet(known_names=known)
        if not sheet.ays:
            if verbose:
                print("[faculty] no status sheet loaded "
                      "(faculty_status.xlsx not found or empty)")
            return
        self._status_sheet = sheet
        applied = 0
        for m in self.members:
            if m.name in sheet.untenured:
                # Explicit marker present (True or False).
                m.untenured_override = sheet.untenured[m.name]
            if m.name in sheet.by_name:
                m.statuses = list(sheet.by_name[m.name])
                applied += 1
        if verbose:
            print(f"[faculty] status sheet: {len(sheet.ays)} AYs, "
                  f"{applied} faculty with entries, "
                  f"active AY = {sheet.active_ay}")
            if sheet.unmatched:
                print(f"[faculty] status sheet unmatched names: "
                      f"{sheet.unmatched}")

    def print_photo_match_table(self) -> None:
        matched = sum(1 for m in self.members if m.photo)
        print(f"[faculty] loaded {len(self.members)} members, "
              f"{matched} photos matched, {len(self.members) - matched} fallback")
        for m in self.members:
            mark = "OK " if m.photo else "-- "
            print(f"  {mark} {m.name:<32} -> {m.photo or '(initials bubble)'}")

    def filter(self, *, tenured: bool | None = None,
               untenured: bool | None = None,
               tenure_track_only: bool = False) -> list[Faculty]:
        out = list(self.members)
        if tenure_track_only:
            out = [m for m in out if m.is_tenure_track]
        if tenured is True:
            out = [m for m in out if m.is_tenured]
        if untenured is True:
            out = [m for m in out if m.rank in RANK_UNTENURED]
        return out


_registry: FacultyRegistry | None = None


def get_registry() -> FacultyRegistry:
    global _registry
    if _registry is None:
        _registry = FacultyRegistry.load(verbose=True)
    return _registry
