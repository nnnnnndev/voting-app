"""Direct unit tests for ballot modules (no storage, no app)."""
import pytest

from app.ballots import approval, ranked, yes_no


def test_yes_no_validate():
    assert yes_no.validate("Yes") == "yes"
    with pytest.raises(ValueError):
        yes_no.validate("maybe")


def test_approval_tally():
    candidates = ["a", "b", "c"]
    ballots = [
        {"type": "approval", "approved": ["a", "b"]},
        {"type": "approval", "approved": ["a"]},
        {"type": "approval", "approved": ["c", "b", "a"]},
    ]
    t = approval.tally(ballots, candidates)
    assert t["counts"] == {"a": 3, "b": 2, "c": 1}
    assert t["ranked"][0]["id"] == "a"
    assert t["total_cast"] == 3


def test_approval_rejects_unknown_candidate():
    with pytest.raises(ValueError):
        approval.serialize(["who?"], {"a", "b"})


def test_approval_dedupes():
    b = approval.serialize(["a", "a", "b"], {"a", "b"})
    assert b["approved"] == ["a", "b"]


def test_ranked_majority_winner():
    cands = ["a", "b", "c"]
    ballots = [{"type": "ranked", "ranking": ["a", "b"]}] * 3 + [
        {"type": "ranked", "ranking": ["b", "a"]},
        {"type": "ranked", "ranking": ["c"]},
    ]
    t = ranked.tally(ballots, cands, seats=1, election_id="t1")
    assert t["winners"] == ["a"]


def test_ranked_elimination():
    # 9 voters. First round: a=4, b=3, c=2. c eliminated; both c-voters
    # have a as 2nd pref → a=6, b=3. a wins with majority.
    cands = ["a", "b", "c"]
    ballots = (
        [{"type": "ranked", "ranking": ["a", "b"]}] * 4
        + [{"type": "ranked", "ranking": ["b", "c"]}] * 3
        + [{"type": "ranked", "ranking": ["c", "a"]}] * 2
    )
    t = ranked.tally(ballots, cands, seats=1, election_id="t2")
    assert t["winners"] == ["a"]
    # Should have taken exactly 2 rounds.
    assert len(t["seat_logs"][0]["rounds"]) == 2


def test_ranked_multi_seat():
    cands = ["a", "b", "c", "d", "e"]
    ballots = (
        [{"type": "ranked", "ranking": ["a", "b", "c"]}] * 4
        + [{"type": "ranked", "ranking": ["b", "c", "a"]}] * 3
        + [{"type": "ranked", "ranking": ["c", "d", "e"]}] * 2
        + [{"type": "ranked", "ranking": ["d", "e"]}]
        + [{"type": "ranked", "ranking": ["e"]}]
    )
    t = ranked.tally(ballots, cands, seats=3, election_id="t3")
    assert len(t["winners"]) == 3
    assert t["winners"][0] == "a"


def test_ranked_partial_allowed():
    b = ranked.serialize(["a"], {"a", "b", "c"}, max_ranks=5)
    assert b["ranking"] == ["a"]


def test_ranked_rejects_duplicate():
    with pytest.raises(ValueError):
        ranked.serialize(["a", "a"], {"a", "b"}, max_ranks=5)


def test_ranked_endorsement_stat():
    """Unranked candidates count as 'not acceptable'; endorsement = times ranked."""
    cands = ["a", "b", "c"]
    ballots = [
        {"type": "ranked", "ranking": ["a", "b"]},   # endorses a, b
        {"type": "ranked", "ranking": ["a"]},        # endorses a only
        {"type": "ranked", "ranking": ["b", "a"]},   # endorses b, a
        {"type": "ranked", "ranking": ["c"]},        # endorses c only
    ]
    t = ranked.tally(ballots, cands, seats=1, election_id="t-endorse")
    assert t["endorsements"] == {"a": 3, "b": 2, "c": 1}
    assert [r["id"] for r in t["endorsements_ranked"]] == ["a", "b", "c"]


def test_ranked_truncates_to_max_ranks():
    b = ranked.serialize(["a", "b", "c", "d", "e", "f"],
                         {"a", "b", "c", "d", "e", "f"}, max_ranks=3)
    assert b["ranking"] == ["a", "b", "c"]
