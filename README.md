# Departmental Voting App

A small Python web app for conducting faculty-meeting votes (motions,
approval voting, ranked-choice elections) inside a department's existing
Microsoft 365 environment. Voters sign in with their institutional account
through Microsoft Entra ID. Ballots are stored in the department's
SharePoint site via Microsoft Graph.

Built originally for the UMass Mechanical & Industrial Engineering
department. Open-sourced under MIT so other academic units can adopt it.

## Why this exists

Hand-raising in faculty meetings amplifies power dynamics and silences
junior colleagues. Online forms work but cannot tally ranked-choice ballots,
do not enforce ballot anonymity, and scatter results across personal
accounts. This app gives departments a permanent, in-house alternative
that lives in their own M365 tenant and SharePoint site.

## Features

- **Three ballot types**: yes/no motions, approval voting, instant-runoff
  ranked-choice with sequential multi-seat IRV.
- **Ballot anonymity by design**: two-store separation between voter
  receipts and ballot contents. See `infra/threat_model.md`.
- **Faculty registry**: loads a CSV of faculty and matches photos by name
  with a tolerant fuzzy matcher.
- **Status sheet**: per-academic-year status records (admin, GPD, sabbatical,
  T/P case, served, chair, etc.) drive automatic eligibility filtering.
  Hard-excluded candidates are greyed out and not selectable; the system
  rejects forged selections.
- **Click-to-rank ballots**: no drag-and-drop required, works on mobile.
- **Endorsement statistic**: ranked-choice results show how many voters
  ranked each candidate at all, surfacing "below the bar" rejection.
- **History panel**: each faculty card has a `+` to expand recent
  AY activity (sabbatical years, GPD terms, prior service).
- **Ad-hoc candidates**: hiring searches and other guests can be added per
  vote with optional photo uploads; photos can be purged after results are
  disseminated.
- **Election templates**: pre-fill ballot type, seats, candidate filter, and
  quorum settings for common votes.
- **Two-phase workflow**: closed nomination votes spawn composition votes
  with the candidate pool pre-filled.
- **Current committee panel**: index page shows the active-AY committee
  composition (voting members, non-voting, alternate) in a collapsible card.

## How to read this repo

- `app/`  FastAPI application code
- `app/ballots/`  ballot type implementations
- `app/anonymity.py`  voter-receipt HMAC, ballot IDs
- `config/rules.yaml`  customization point: branding, statuses, templates,
  AY columns, name aliases
- `infra/`  documents for IT review (Entra app registration spec, threat
  model, email draft, ServiceNow notes)
- `tests/`  unit and integration tests

## Adopting this app for another department

See `ADOPTION.md` for step-by-step instructions. The short version:

1. Clone or fork this repo.
2. Edit `config/rules.yaml` to set your branding, status codes, election
   templates, and academic-year column labels.
3. Replace `faculty_list.csv.template` with your real faculty list saved as
   `faculty list.csv`.
4. Replace `faculty_status.csv.template` with your real status sheet.
5. Drop faculty photos into `faculty photos/`.
6. Register an Entra application in your tenant (see `infra/app_registration.md`).
7. Run locally, then deploy to your institutional hosting.

## Local development

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# Edit .env to fill in Entra and session values, or set MIE_DEV_AUTH=1 to
# bypass Entra entirely while testing.
uvicorn app.main:app --reload --port 8000
```

Browse to `http://localhost:8000`.

## License

MIT. See `LICENSE`.

## Status

Production-ready for departmental use after IT provisions an Entra app
registration and SharePoint storage. Currently runs against local JSON
storage; the `GraphStorage` SharePoint backend is a small swap once IT
grants `Sites.Selected` write on a site.
