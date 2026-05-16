# Draft email to UMass IT

**Suggested recipient:** UMass Amherst IT, Enterprise Applications group, or
the identity/Entra team. If you don't know the right address, start at the
help desk (it@umass.edu) and ask them to route to the right team for
"Entra ID app registration and small departmental application hosting."

**Subject line options (pick one):**
- Departmental app for MIE faculty voting: Entra registration and hosting question
- MIE Voting App: requesting Sites.Selected scope and hosting guidance

---

Hello,

I'm Stephen Nonnenmann, Professor in MIE. I've put together a small
Python web app for departmental faculty votes (motions, approval voting,
ranked choice) and I'd like to host it in our M365 environment so the
ballot data lives in the department's SharePoint site.

Two questions:

1. **Entra app registration.** Can I register the app in the UMass
   tenant myself, or does this need to go through your team? Requested
   permissions are minimal: `User.Read` (delegated, sign-in only) and
   `Sites.Selected` (application, scoped to the MIE SharePoint site,
   nothing tenant-wide). Details in the attached `app_registration.md`.

2. **Hosting.** Is there a departmental Azure subscription I can use, or
   should this run on a dept VM or other infrastructure you'd recommend?
   It's a single FastAPI process, well under 200 MB resident memory, no
   database, outbound HTTPS to Microsoft Graph only.

Attached: app registration spec and a short threat model. Full source
available on request.

Thanks,

Stephen Nonnenmann
Professor, MIE
snonnenmann@umass.edu

---

## What to attach / share

When you send the email, include:

1. **`infra/app_registration.md`**: the Entra spec (attach as PDF or .md)
2. **`infra/threat_model.md`**: the threat model
3. **Source code access.** Two options:
   - Easiest: zip up the project folder (excluding `.venv/`, `data/`,
     `__pycache__/`) and attach. About 50 KB.
   - Better long-term: push to a private GitHub or UMass-hosted GitLab
     repo and share read access with IT.

To zip excluding the heavy folders, in PowerShell from the project root:

```powershell
Get-ChildItem -Recurse -File |
  Where-Object { $_.FullName -notmatch '\\\\.venv\\\\|\\\\data\\\\|__pycache__|\\\\.pytest_cache\\\\' } |
  Compress-Archive -DestinationPath .\\MIEVotingApp.zip -Force
```

---

## What you are formally asking Azure / IT for

In Azure/Entra terminology, the asks are:

1. **An Entra ID app registration** in the UMass tenant, single-tenant,
   with a web platform redirect URI (initially `http://localhost:8000/auth/callback`
   for dev, plus a production URL once hosting is decided).

2. **Admin consent** for the two permissions in the spec:
   - `User.Read` (delegated)
   - `Sites.Selected` (application)

3. **A `Sites.Selected` write grant on one specific SharePoint site:**
   the MIE department site. This is granted via Microsoft Graph after
   the app registration exists; IT or the site owner can do it.

4. **Hosting decision:** Azure App Service under a departmental
   subscription is the smoothest option, but a departmental VM works
   too. The app needs Python 3.11+ and outbound HTTPS to Microsoft Graph.

5. **A client secret** for the app registration, stored only on the host
   in environment variables. Rotation every 6 months.

That's the full ask. Everything else (database, file storage, user
management) is handled inside the existing M365 ecosystem.
