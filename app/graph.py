"""Microsoft Graph client for reading/writing ballots in SharePoint.

Uses **app-only** authentication (client credentials flow), not the voter's
delegated token. This is deliberate: see anonymity.py and
infra/threat_model.md. The app's permissions should be `Sites.Selected`
scoped to one SharePoint site only.
"""
from __future__ import annotations

import httpx
import msal

from .config import settings

GRAPH = "https://graph.microsoft.com/v1.0"


def _app_token() -> str:
    app = msal.ConfidentialClientApplication(
        client_id=settings.azure_client_id,
        client_credential=settings.azure_client_secret,
        authority=settings.authority,
    )
    result = app.acquire_token_for_client(
        scopes=["https://graph.microsoft.com/.default"]
    )
    if "access_token" not in result:
        raise RuntimeError(f"Failed to acquire app token: {result}")
    return result["access_token"]


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=GRAPH,
        headers={"Authorization": f"Bearer {_app_token()}"},
        timeout=20.0,
    )


def get_site_id() -> str:
    """Resolve the SharePoint site to its Graph ID."""
    host = settings.sharepoint_hostname
    path = settings.sharepoint_site_path
    with _client() as c:
        r = c.get(f"/sites/{host}:{path}")
        r.raise_for_status()
        return r.json()["id"]


# Stubs to be implemented next:
#
# def create_election(site_id, election) -> str: ...
# def append_ballot(site_id, election_id, ballot_blob) -> None: ...
# def tally(site_id, election_id) -> dict: ...
#
# Ballots will be stored as one JSON file per ballot in a folder named
# by election_id, so no single file is ever rewritten (avoids races and
# preserves an append-only audit trail).
