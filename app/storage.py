"""Storage abstraction.

Two implementations:
  - LocalStorage: writes JSON files under ./data/. Used for local dev so we
    can build and test the whole flow before UMass IT provisions the Entra
    app registration.
  - GraphStorage: writes to a SharePoint document library via Microsoft
    Graph. To be implemented in graph.py once we have an app registration.

Both implement the same interface so the rest of the app doesn't care.

Layout on disk (mirrored in SharePoint later):

  data/
    elections/<election_id>.json           election metadata (incl. salt)
    voters/<election_id>/<receipt>.txt     empty marker = "this voter voted"
    ballots/<election_id>/<ballot_id>.json ballot content, no voter link
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterator


class Storage(ABC):
    @abstractmethod
    def put_election(self, election_id: str, data: dict) -> None: ...

    @abstractmethod
    def get_election(self, election_id: str) -> dict | None: ...

    @abstractmethod
    def list_elections(self) -> list[dict]: ...

    @abstractmethod
    def has_voted(self, election_id: str, receipt: str) -> bool: ...

    @abstractmethod
    def mark_voted(self, election_id: str, receipt: str) -> None: ...

    @abstractmethod
    def put_ballot(self, election_id: str, ballot_id: str, ballot: dict) -> None: ...

    @abstractmethod
    def iter_ballots(self, election_id: str) -> Iterator[dict]: ...


class LocalStorage(Storage):
    def __init__(self, root: Path | str = "data") -> None:
        self.root = Path(root)
        (self.root / "elections").mkdir(parents=True, exist_ok=True)
        (self.root / "voters").mkdir(parents=True, exist_ok=True)
        (self.root / "ballots").mkdir(parents=True, exist_ok=True)

    def put_election(self, election_id: str, data: dict) -> None:
        path = self.root / "elections" / f"{election_id}.json"
        path.write_text(json.dumps(data, indent=2))
        (self.root / "voters" / election_id).mkdir(exist_ok=True)
        (self.root / "ballots" / election_id).mkdir(exist_ok=True)

    def get_election(self, election_id: str) -> dict | None:
        path = self.root / "elections" / f"{election_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def list_elections(self) -> list[dict]:
        out = []
        for p in sorted((self.root / "elections").glob("*.json")):
            out.append(json.loads(p.read_text()))
        return out

    def has_voted(self, election_id: str, receipt: str) -> bool:
        return (self.root / "voters" / election_id / receipt).exists()

    def mark_voted(self, election_id: str, receipt: str) -> None:
        (self.root / "voters" / election_id / receipt).touch()

    def put_ballot(self, election_id: str, ballot_id: str, ballot: dict) -> None:
        path = self.root / "ballots" / election_id / f"{ballot_id}.json"
        path.write_text(json.dumps(ballot, indent=2))

    def iter_ballots(self, election_id: str) -> Iterator[dict]:
        folder = self.root / "ballots" / election_id
        if not folder.exists():
            return
        for p in folder.glob("*.json"):
            yield json.loads(p.read_text())


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        _storage = LocalStorage()
    return _storage


def set_storage(s: Storage) -> None:
    global _storage
    _storage = s
