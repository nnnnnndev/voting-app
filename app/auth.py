"""Entra ID (Azure AD) OAuth via MSAL, plus a dev-mode fake login.

Voters sign in with their UMass account. We use the authorization code flow
with a confidential client (the app has a client secret stored server-side).

The session cookie holds only the voter's stable object ID (oid) and display
name — never the access token. Graph calls go through a separate app-only
token (see graph.py), which is the key to the anonymity story: the user's
delegated token is never used to write ballots, so ballots in SharePoint
carry no link back to the signed-in user.

DEV MODE: if the env var MIE_DEV_AUTH=1 is set, /auth/login presents a tiny
form to "sign in" as any name+oid. This lets us test the full voting flow
without an Entra app registration. Disable in production.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter(prefix="/auth", tags=["auth"])

LOGIN_SCOPES = ["User.Read"]


def _dev_mode() -> bool:
    return os.environ.get("MIE_DEV_AUTH") == "1"


def _msal_app():
    # Imported lazily so dev mode works without .env populated.
    import msal

    from .config import settings

    return msal.ConfidentialClientApplication(
        client_id=settings.azure_client_id,
        client_credential=settings.azure_client_secret,
        authority=settings.authority,
    )


@router.get("/login")
def login(request: Request):
    if _dev_mode():
        return HTMLResponse(
            """
            <h2>Dev sign-in</h2>
            <p><i>MIE_DEV_AUTH=1 — Entra is bypassed.</i></p>
            <form method="post" action="/auth/dev-login">
              <label>Name: <input name="name" value="Test Faculty"></label><br>
              <label>OID:  <input name="oid"  value="oid-test-1"></label><br>
              <button type="submit">Sign in</button>
            </form>
            """
        )

    from .config import settings

    flow = _msal_app().initiate_auth_code_flow(
        scopes=LOGIN_SCOPES, redirect_uri=settings.azure_redirect_uri
    )
    request.session["auth_flow"] = flow
    return RedirectResponse(flow["auth_uri"])


@router.post("/dev-login")
def dev_login(request: Request, name: str = Form(...), oid: str = Form(...)):
    if not _dev_mode():
        raise HTTPException(404, "Not found")
    request.session["voter"] = {"oid": oid, "name": name, "upn": f"{oid}@dev"}
    return RedirectResponse("/", status_code=303)


@router.get("/callback")
def callback(request: Request):
    flow = request.session.pop("auth_flow", None)
    if not flow:
        raise HTTPException(400, "No auth flow in session")
    result = _msal_app().acquire_token_by_auth_code_flow(
        flow, dict(request.query_params)
    )
    if "error" in result:
        raise HTTPException(400, result.get("error_description", "Auth failed"))
    claims = result.get("id_token_claims", {})
    request.session["voter"] = {
        "oid": claims["oid"],
        "name": claims.get("name", ""),
        "upn": claims.get("preferred_username", ""),
    }
    return RedirectResponse("/")


@router.get("/logout")
def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse("/")


def current_voter(request: Request) -> dict | None:
    return request.session.get("voter")
