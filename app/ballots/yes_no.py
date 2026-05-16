"""Yes / No / Abstain ballot.

The simplest ballot type — a motion. Each voter picks exactly one of
{yes, no, abstain}. Tally is a count of each choice; abstentions are
reported but do not count toward yes/no totals.
"""
from __future__ import annotations

from collections import Counter
from typing import Iterable

CHOICES = ("yes", "no", "abstain")


def validate(choice: str) -> str:
    c = (choice or "").strip().lower()
    if c not in CHOICES:
        raise ValueError(f"choice must be one of {CHOICES}, got {choice!r}")
    return c


def serialize(choice: str) -> dict:
    return {"type": "yes_no", "choice": validate(choice)}


def tally(ballots: Iterable[dict]) -> dict:
    counts: Counter[str] = Counter()
    for b in ballots:
        if b.get("type") != "yes_no":
            continue
        counts[b["choice"]] += 1

    yes = counts.get("yes", 0)
    no = counts.get("no", 0)
    abstain = counts.get("abstain", 0)
    total_cast = yes + no + abstain
    decisive = yes + no

    return {
        "type": "yes_no",
        "yes": yes,
        "no": no,
        "abstain": abstain,
        "total_cast": total_cast,
        "passed": yes > no if decisive > 0 else None,
    }
