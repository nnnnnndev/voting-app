# Entra App Registration: Spec for UMass IT

This document specifies the Microsoft Entra ID application registration
required to run the MIE Voting App. It is written to be handed to UMass IT
security/identity staff so they can review and provision the registration.

## Application

- **Display name:** MIE Voting App
- **Supported account types:** Single tenant (UMass only)
- **Owner:** Prof. Stephen Nonnenmann, MIE Department

## Redirect URIs (Web platform)

- `http://localhost:8000/auth/callback` (local development only)
- `https://<production-host>/auth/callback` (to be assigned by IT)

## API permissions

The app uses **two distinct auth flows**, deliberately:

### Delegated (signed-in user)
Used only to verify the voter's identity at sign-in.

| Permission     | Type      | Admin consent | Why                                      |
|----------------|-----------|---------------|------------------------------------------|
| `User.Read`    | Delegated | No            | Read the signed-in user's basic profile. |

The app **does not** request delegated SharePoint or Files permissions.
Ballots are never written using the voter's token.

### Application (app-only)
Used to write ballots to SharePoint. Scoped to a single site.

| Permission         | Type        | Admin consent | Why                                          |
|--------------------|-------------|---------------|----------------------------------------------|
| `Sites.Selected`   | Application | Yes           | Read/write only the specific MIE SharePoint site, nothing else in the tenant. |

After admin consent, the SharePoint site owner grants the app `write`
access to the specific site via the
[`/sites/{site-id}/permissions`](https://learn.microsoft.com/en-us/graph/api/site-post-permissions)
Graph endpoint. No other site in the tenant is reachable by the app.

## Client secret

- Stored server-side only, in environment variables on the host (never in
  source control).
- Rotation: every 6 months, or immediately on any suspected compromise.

## Token lifetimes

- Default Entra lifetimes are acceptable. No custom token policy required.

## Sign-in audience

- Restricted to UMass faculty/staff via a group-based assignment (group to
  be created by IT, populated by the MIE department).

## What this app does NOT do

- Does not read any user's mail, calendar, files, or contacts.
- Does not enumerate users beyond the signed-in voter.
- Does not access any tenant resource outside the single SharePoint site
  granted via `Sites.Selected`.
- Does not store voter identity alongside ballot contents (see
  `threat_model.md`).
