"""Approval voting.

Voter checks any subset of candidates. Tally is the count of approvals per
candidate. Used for nomination rounds.

Ballot shape on disk:
    {"type": "approval", "approved": ["faculty_id_1", "faculty_id_2", ...]}
"""
from __future__ import annotations

from collections import Counter
from typing import Iterable


def validate(approved: list[str], candidate_ids: set[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for cid in approved:
        if cid not in candidate_ids:
            raise ValueError(f"unknown candidate: {cid}")
        if cid in seen:
            continue
        seen.add(cid)
        out.append(cid)
    return out


def serialize(approved: list[str], candidate_ids: set[str]) -> dict:
    return {"type": "approval", "approved": validate(approved, candidate_ids)}


def tally(ballots: Iterable[dict], candidate_ids: list[str]) -> dict:
    counts: Counter[str] = Counter({cid: 0 for cid in candidate_ids})
    total = 0
    for b in ballots:
        if b.get("type") != "approval":
            continue
        total += 1
        for cid in b.get("approved", []):
            if cid in counts:
                counts[cid] += 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return {
        "type": "approval",
        "total_cast": total,
        "counts": dict(counts),
        "ranked": [{"id": cid, "approvals": n} for cid, n in ranked],
    }
