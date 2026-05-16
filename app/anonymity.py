"""The trust-critical anonymity layer.

PROBLEM
-------
The system must enforce two things that are in tension:
  1. Only eligible faculty can vote, and each faculty member votes at most
     once per election. (Requires knowing who voted.)
  2. A stored ballot cannot be linked back to the voter, even by someone
     with access to the SharePoint site or the app's logs. (Requires NOT
     knowing who cast which ballot.)

DESIGN
------
Two separate stores per election:

  voters/<election_id>/<hash(oid|election_salt)>   -- "this person voted"
  ballots/<election_id>/<random_uuid>.json         -- ballot contents

The voter-receipt store contains only an HMAC of the voter's Entra object ID
with a per-election salt. It records that they voted, nothing else. The
ballot store contains the ballot, with NO voter identifier. The two stores
are written in separate Graph calls and the app does not log the pairing.

This is not perfect — an attacker with full server access during a live
election could correlate by timing. Mitigations documented in
infra/threat_model.md include buffered writes and post-election shuffling.

For now this module is a stub; real implementation lands once the Graph
client is wired up.
"""
from __future__ import annotations

import hmac
import hashlib
import secrets


def voter_receipt(voter_oid: str, election_salt: str) -> str:
    """Stable per-election pseudonym for a voter. Used only to prevent
    double-voting; reveals nothing about ballot contents."""
    return hmac.new(
        election_salt.encode(),
        voter_oid.encode(),
        hashlib.sha256,
    ).hexdigest()


def new_election_salt() -> str:
    return secrets.token_urlsafe(32)


def new_ballot_id() -> str:
    return secrets.token_urlsafe(16)
