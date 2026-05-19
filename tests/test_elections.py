from pathlib import Path

import pytest

from app import elections
from app.storage import LocalStorage


@pytest.fixture
def storage(tmp_path: Path) -> LocalStorage:
    return LocalStorage(tmp_path)


def _yn(storage, **kw):
    return elections.create_election(
        title=kw.get("title", "M"),
        description="",
        template_id="general_motion",
        created_by_oid=kw.get("by", "prof-1"),
        storage=storage,
    )


def test_create_and_get(storage):
    e = _yn(storage, title="Approve curriculum change?")
    got = elections.get_election(e.id, storage=storage)
    assert got.title == e.title
    assert got.status == "open"
    assert got.salt == e.salt
    assert got.ballot_type == "yes_no"


def test_yes_no_tally(storage):
    e = _yn(storage)
    elections.cast_vote(e.id, "voter-a", {"choice": "yes"}, storage=storage)
    elections.cast_vote(e.id, "voter-b", {"choice": "yes"}, storage=storage)
    elections.cast_vote(e.id, "voter-c", {"choice": "no"}, storage=storage)
    elections.cast_vote(e.id, "voter-d", {"choice": "abstain"}, storage=storage)
    t = elections.tally(e.id, storage=storage)
    assert t["yes"] == 2 and t["no"] == 1 and t["abstain"] == 1
    assert t["passed"] is True


def test_double_vote_rejected(storage):
    e = _yn(storage)
    elections.cast_vote(e.id, "voter-a", {"choice": "yes"}, storage=storage)
    with pytest.raises(elections.AlreadyVoted):
        elections.cast_vote(e.id, "voter-a", {"choice": "no"}, storage=storage)


def test_closed_election_rejects_votes(storage):
    e = _yn(storage)
    elections.cast_vote(e.id, "voter-a", {"choice": "yes"}, storage=storage)
    elections.close_election(e.id, "prof-1", storage=storage)
    with pytest.raises(elections.ElectionClosed):
        elections.cast_vote(e.id, "voter-b", {"choice": "yes"}, storage=storage)


def test_only_creator_can_close(storage):
    e = _yn(storage, by="prof-1")
    with pytest.raises(elections.NotPermitted):
        elections.close_election(e.id, "prof-2", storage=storage)


def test_anonymity_no_voter_id_in_ballots(storage):
    e = _yn(storage)
    elections.cast_vote(e.id, "voter-secret-oid", {"choice": "yes"}, storage=storage)
    ballots = list(storage.iter_ballots(e.id))
    assert len(ballots) == 1
    assert "voter-secret-oid" not in str(ballots[0])


def test_excluded_voter_rejected(storage):
    e = elections.create_election(
        title="M",
        description="",
        template_id="general_motion",
        created_by_oid="prof-1",
        excluded_oids=["recused-voter"],
        storage=storage,
    )
    with pytest.raises(elections.NotEligible):
        elections.cast_vote(e.id, "recused-voter", {"choice": "yes"}, storage=storage)


def test_tie_not_passed(storage):
    e = _yn(storage)
    elections.cast_vote(e.id, "a", {"choice": "yes"}, storage=storage)
    elections.cast_vote(e.id, "b", {"choice": "no"}, storage=storage)
    t = elections.tally(e.id, storage=storage)
    assert t["passed"] is False


def test_ad_hoc_candidates_in_ranked_vote(storage):
    """Custom ranked vote with two external candidates, no faculty."""
    extras = [
        {"id": "ext_aaa", "name": "Jane Q. Candidate", "rank": "Asst. Prof., MIT", "photo": None},
        {"id": "ext_bbb", "name": "John R. Candidate", "rank": "Postdoc, Stanford", "photo": "ext_bbb.jpg"},
    ]
    e = elections.create_election(
        title="Faculty search — final shortlist",
        description="",
        template_id="custom_ranked",
        created_by_oid="prof-1",
        candidate_oids=[],  # no faculty
        extra_candidates=extras,
        seats=1,
        max_ranks=2,
        storage=storage,
    )
    assert "ext_aaa" in e.candidate_oids
    assert "ext_bbb" in e.candidate_oids
    assert e.extra_candidates == extras

    elections.cast_vote(e.id, "v1", {"ranking": ["ext_aaa", "ext_bbb"]}, storage=storage)
    elections.cast_vote(e.id, "v2", {"ranking": ["ext_aaa"]}, storage=storage)
    elections.cast_vote(e.id, "v3", {"ranking": ["ext_bbb", "ext_aaa"]}, storage=storage)

    t = elections.tally(e.id, storage=storage)
    assert t["winners"] == ["ext_aaa"]


def test_delete_election_removes_all_traces(storage):
    e = _yn(storage)
    elections.cast_vote(e.id, "voter-a", {"choice": "yes"}, storage=storage)
    elections.cast_vote(e.id, "voter-b", {"choice": "no"}, storage=storage)
    elections.close_election(e.id, "prof-1", storage=storage)
    assert any(storage.iter_ballots(e.id))

    elections.delete_election(e.id, "prof-1", storage=storage)

    with pytest.raises(elections.ElectionNotFound):
        elections.get_election(e.id, storage=storage)
    assert not list(storage.iter_ballots(e.id))


def test_only_creator_can_delete(storage):
    e = _yn(storage, by="prof-1")
    with pytest.raises(elections.NotPermitted):
        elections.delete_election(e.id, "prof-2", storage=storage)
    # Election still exists.
    elections.get_election(e.id, storage=storage)


def test_scheduled_close_auto_transitions(storage):
    """An open election with closes_at in the past auto-closes on read."""
    import time
    e = elections.create_election(
        title="Time-limited", description="", template_id="general_motion",
        created_by_oid="prof-1", closes_at=time.time() - 1,  # already past
        storage=storage,
    )
    # On a fresh read it should appear closed.
    got = elections.get_election(e.id, storage=storage)
    assert got.status == "closed"
    # Casting should be rejected.
    with pytest.raises(elections.ElectionClosed):
        elections.cast_vote(e.id, "voter-a", {"choice": "yes"}, storage=storage)


def test_scheduled_close_future_stays_open(storage):
    import time
    e = elections.create_election(
        title="Future close", description="", template_id="general_motion",
        created_by_oid="prof-1", closes_at=time.time() + 3600,
        storage=storage,
    )
    got = elections.get_election(e.id, storage=storage)
    assert got.status == "open"
    elections.cast_vote(e.id, "voter-a", {"choice": "yes"}, storage=storage)


def test_ad_hoc_round_trip(storage):
    """Extras survive a storage round-trip (write + read)."""
    extras = [{"id": "ext_x", "name": "Jane", "rank": "", "photo": None}]
    e = elections.create_election(
        title="t", description="", template_id="custom_approval",
        created_by_oid="p", candidate_oids=[], extra_candidates=extras,
        storage=storage,
    )
    got = elections.get_election(e.id, storage=storage)
    assert got.extra_candidates == extras
