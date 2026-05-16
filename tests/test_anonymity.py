from app.anonymity import new_ballot_id, new_election_salt, voter_receipt


def test_voter_receipt_is_stable():
    salt = "fixed-salt"
    a = voter_receipt("user-oid-1", salt)
    b = voter_receipt("user-oid-1", salt)
    assert a == b


def test_voter_receipt_differs_across_elections():
    a = voter_receipt("user-oid-1", new_election_salt())
    b = voter_receipt("user-oid-1", new_election_salt())
    assert a != b


def test_voter_receipt_differs_across_users():
    salt = new_election_salt()
    assert voter_receipt("user-1", salt) != voter_receipt("user-2", salt)


def test_ballot_ids_unique():
    ids = {new_ballot_id() for _ in range(1000)}
    assert len(ids) == 1000
