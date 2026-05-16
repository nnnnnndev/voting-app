"""Ballot type implementations.

Each ballot type is a small module that knows how to:
  - validate a submitted ballot
  - serialize it to JSON for storage
  - tally a collection of ballots into a result

Planned types:
  - yes_no.py         simple motion: yes / no / abstain
  - approval.py       check any number of candidates
  - ranked.py         instant-runoff / ranked choice
  - multi_seat.py     pick K of N (committee composition)
"""
