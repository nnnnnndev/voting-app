"""Ranked-choice (instant-runoff) voting.

Voters rank candidates 1..N. Partial rankings are allowed. Tally is IRV:
in each round, count first-place votes (skipping candidates already
eliminated); if a candidate has a majority of remaining votes, they win.
Otherwise, the candidate with the fewest first-place votes is eliminated
and the round repeats.

For multi-seat elections we run IRV repeatedly: winner is removed from all
ballots and the next seat is filled, until `seats` winners are chosen.
This is a simple "sequential IRV" — not Single Transferable Vote, which
would require quota-based fractional transfers. Sequential IRV is the
standard departmental-scale choice and is what we tally here.

Tie-breaking on elimination: candidate eliminated in a prior round count
backwards (Borda-style backup) — but for simplicity v1 we use a seeded
random tie-break and log the seed, as documented in threat_model.md.

Ballot shape on disk:
    {"type": "ranked", "ranking": ["faculty_id_1", "faculty_id_2", ...]}
"""
from __future__ import annotations

import hashlib
import random
from collections import Counter
from typing import Iterable


def validate(ranking: list[str], candidate_ids: set[str], max_ranks: int) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for cid in ranking:
        if cid not in candidate_ids:
            raise ValueError(f"unknown candidate: {cid}")
        if cid in seen:
            raise ValueError(f"candidate ranked twice: {cid}")
        seen.add(cid)
        out.append(cid)
        if len(out) >= max_ranks:
            break
    if not out:
        raise ValueError("must rank at least one candidate")
    return out


def serialize(ranking: list[str], candidate_ids: set[str], max_ranks: int) -> dict:
    return {"type": "ranked", "ranking": validate(ranking, candidate_ids, max_ranks)}


def _irv_round_winner(
    ballots: list[list[str]],
    candidates: set[str],
    seed: str,
) -> tuple[str, list[dict]]:
    """Run IRV among `candidates` over `ballots`. Returns (winner_id, rounds_log)."""
    rng = random.Random(seed)
    rounds = []
    active = set(candidates)
    while True:
        counts: Counter[str] = Counter({c: 0 for c in active})
        exhausted = 0
        for ranking in ballots:
            top = next((c for c in ranking if c in active), None)
            if top is None:
                exhausted += 1
            else:
                counts[top] += 1
        total = sum(counts.values())
        rounds.append({
            "counts": dict(counts),
            "exhausted": exhausted,
        })
        if total == 0:
            # Everyone exhausted; pick deterministically from remaining.
            winner = sorted(active)[0] if active else ""
            return winner, rounds
        leader, lead_count = max(counts.items(), key=lambda kv: kv[1])
        if lead_count * 2 > total:
            return leader, rounds
        # Eliminate lowest, breaking ties with the seeded RNG.
        min_count = min(counts.values())
        bottom = [c for c, n in counts.items() if n == min_count]
        if len(active) - len(bottom) < 1:
            # Final tie. Pick one with seeded RNG.
            winner = rng.choice(sorted(bottom))
            return winner, rounds
        eliminated = rng.choice(sorted(bottom))
        active.discard(eliminated)
        rounds[-1]["eliminated"] = eliminated


def tally(
    ballots: Iterable[dict],
    candidate_ids: list[str],
    seats: int = 1,
    election_id: str = "",
) -> dict:
    """Sequential IRV for `seats` seats. Returns winners in seat order."""
    rankings: list[list[str]] = []
    for b in ballots:
        if b.get("type") != "ranked":
            continue
        rankings.append(list(b.get("ranking", [])))

    # Endorsement count: how many ballots ranked each candidate at all.
    # Unranked = "not acceptable to this voter."
    endorsements: dict[str, int] = {cid: 0 for cid in candidate_ids}
    for r in rankings:
        for cid in set(r):
            if cid in endorsements:
                endorsements[cid] += 1

    remaining = set(candidate_ids)
    winners: list[str] = []
    seat_logs: list[dict] = []
    seed_base = hashlib.sha256(election_id.encode()).hexdigest()
    for seat in range(seats):
        if not remaining:
            break
        seat_seed = f"{seed_base}:seat{seat}"
        # Strip already-elected from ballots.
        stripped = [[c for c in r if c not in set(winners)] for r in rankings]
        winner, rounds = _irv_round_winner(stripped, remaining, seat_seed)
        if not winner:
            break
        winners.append(winner)
        remaining.discard(winner)
        seat_logs.append({"seat": seat + 1, "winner": winner, "rounds": rounds})

    # Ranked endorsement summary, sorted by endorsement count desc.
    endorsement_ranked = sorted(
        candidate_ids,
        key=lambda cid: (-endorsements[cid], cid),
    )
    return {
        "type": "ranked",
        "total_cast": len(rankings),
        "seats": seats,
        "winners": winners,
        "seat_logs": seat_logs,
        "endorsements": endorsements,
        "endorsements_ranked": [
            {"id": cid, "count": endorsements[cid]}
            for cid in endorsement_ranked
        ],
    }
