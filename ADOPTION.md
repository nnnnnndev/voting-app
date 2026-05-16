# Adopting this app for your department

A step-by-step guide for another academic unit to deploy this voting app
in its own Microsoft 365 environment.

The instructions assume your institution uses Microsoft 365 (Entra ID,
SharePoint) and your department has a SharePoint site. If your institution
runs Google Workspace instead, this app does not apply.

## 1. Clone the repository

```
git clone <repo-url> voting-app
cd voting-app
```

Or download a zip and extract.

## 2. Replace the data files

The repo ships with template files containing synthetic data. Replace them
with your real personnel data, which stays on your local filesystem and is
gitignored by default.

**Faculty list.** Save your faculty as `faculty list.csv` (note the space)
in the project root, in this format:

```
Name, Rank
Jane Q. Faculty,Professor
John K. Faculty,Associate Professor
Alex T. Faculty,Assistant Professor
Pat L. Lecturer,Senior Lecturer
```

Ranks may be `Professor`, `Associate Professor`, `Assistant Professor`,
`Lecturer`, or `Senior Lecturer`. The app uses rank to derive the default
candidate pool for tenured/untenured templates.

**Faculty photos.** Put photos in a folder named `faculty photos/`. The
matcher pairs photos to faculty by token overlap, so filenames like
`smith.jpg`, `Jane_Smith.png`, or `smith-headshot.webp` all work for a
faculty member named Jane Smith. Unmatched faculty get a UMass-red initials
bubble. The match table prints on startup so you can spot any mismatches.

Supported image formats: JPG, JPEG, PNG, WEBP, GIF.

**Faculty status sheet.** This is the per-AY personnel record that drives
eligibility filtering and the history panel. Save it as
`faculty status.csv` (or any name matching `dpc history*.csv`,
`dpc_status*.csv`, etc., see `app/faculty_status.py` for the glob list).

Format is headerless CSV with columns:

```
<untenured marker>,<short name>,<AY 1>,<AY 2>,<AY 3>,...
```

- The untenured marker column holds free text (e.g. "Pre-tenure") for
  faculty who are untenured but appear in the tenured pool by rank
  (Associate Professor not yet tenured). Leave blank for tenured faculty.
- Short name is the first name or nickname used in the sheet; alternate
  spellings map via `name_aliases` in `config/rules.yaml`.
- AY columns hold status keywords like `Served`, `Chair`, `Admin`, `GPD`,
  `T/P Case`, `Sabbatical`, etc. Blank means no special status.

A legend block at the bottom of the CSV is ignored by the loader (it stops
parsing at the first row whose column 0 starts with `LEGEND`).

## 3. Edit `config/rules.yaml`

This is the main customization point. Open the file and edit:

**Branding**

```yaml
branding:
  app_name: "Your Voting App"
  primary_color: "#003366"
  footer_note: "Your unit  internal use  ballots stored in your SharePoint site"
```

Pick your department or institution color (any hex). All derived shades
(button hover, soft tints, selected-card highlights) propagate from this
single value via CSS `color-mix()`.

**Academic-year columns**

```yaml
ay_columns:
  - "AY 23-24"
  - "AY 24-25"
  - "AY 25-26"
  - "AY 26-27"
```

The rightmost AY is the active one, used for eligibility filtering.
Each year, you add a new entry at the end of this list and add a new
column to the status CSV.

**Status codes**

```yaml
statuses:
  ADMIN:           { label: "Admin",        hard_exclude: true,  aliases: ["admin"] }
  SABBATICAL:      { label: "Sabbatical",   hard_exclude: true,  aliases: ["sabbatical"] }
  SERVED:          { label: "Served",       hard_exclude: false, aliases: ["served"] }
  ...
```

Each status has:
- `label`: how it appears in history badges and tags
- `hard_exclude`: if true, faculty with this status in the active AY are
  greyed out and cannot be voted for
- `aliases`: alternate spellings the parser accepts in CSV cells

Add or remove statuses to match your committee rules. Local statuses like
`GRADUATE_COMMITTEE` or `RESEARCH_DEAN` are fine to add.

**Election templates**

```yaml
templates:
  general_motion:
    label: "General motion (Yes / No / Abstain)"
    description: "A simple motion."
    ballot_type: "yes_no"
  composition:
    label: "Committee composition (ranked)"
    ballot_type: "ranked"
    seats: 5
    max_ranks: 5
    candidate_filter: "tenured"
    require_quorum: true
```

`ballot_type` is one of `yes_no`, `approval`, `ranked`.
`candidate_filter` is one of `none`, `tenured`, `untenured`, `tenure_track`.

**Name aliases**

```yaml
name_aliases:
  Matt: "Matthew Lackner"
  Steve dBK: "Stephen de Bruyn Kops"
```

Only needed when the short name in the status CSV does not auto-resolve
to a unique faculty entry (e.g., two faculty share a first name).

## 4. Register an Entra application

See `infra/app_registration.md` for the exact spec. Summary:

1. Request an administrative subsidiary account from your institution's
   identity team.
2. Sign into `portal.azure.com` with that account.
3. Microsoft Entra ID -> App registrations -> New registration.
4. Name: your app name. Account types: single tenant. Redirect URI:
   `http://localhost:8000/auth/callback` (Web platform) for development.
5. Note the Application (client) ID and Directory (tenant) ID.
6. API permissions: add Microsoft Graph delegated `User.Read` and
   application `Sites.Selected`.
7. Certificates & secrets: create a client secret, copy the Value.
8. Submit any authorization request your institution requires (at UMass
   this is a ServiceNow form; other institutions vary).

Once your IT grants the `Sites.Selected` write permission to your
SharePoint site, fill in `SHAREPOINT_HOSTNAME` and `SHAREPOINT_SITE_PATH`
in your `.env`.

## 5. Configure environment

Copy `.env.example` to `.env` and fill in:

```
AZURE_TENANT_ID=...        # Directory (tenant) ID
AZURE_CLIENT_ID=...        # Application (client) ID
AZURE_CLIENT_SECRET=...    # Client secret Value (not Secret ID)
AZURE_REDIRECT_URI=http://localhost:8000/auth/callback
SHAREPOINT_HOSTNAME=       # e.g. yourorg.sharepoint.com
SHAREPOINT_SITE_PATH=      # e.g. /sites/YourDeptSite
SESSION_SECRET=...         # random string, see comment in .env.example
```

## 6. Run locally

```
python -m venv .venv
.\.venv\Scripts\activate     # Windows
# source .venv/bin/activate   # macOS / Linux
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Visit `http://localhost:8000`. Sign in with your institutional account.

For testing without Entra during initial development, set
`MIE_DEV_AUTH=1` in the shell environment and the app uses a local
sign-in form instead of Entra.

## 7. Deploy

Two common paths:

**Azure App Service.** Recommended if your institution has a departmental
Azure subscription. Update the redirect URI in the Entra app registration
to your production URL.

**Departmental VM.** Run uvicorn behind a reverse proxy (nginx, Caddy) on
a small Linux server in your department.

In either case, the data lives in your SharePoint site via Microsoft Graph,
not on the host running the app. The app is stateless except for session
cookies.

## 8. Annual maintenance

Each May (or whenever you compose committees for the next year):

1. Add a new AY column to `faculty status.csv` and a matching entry to
   `ay_columns` in `config/rules.yaml`.
2. Fill in known statuses for the upcoming AY (planned sabbaticals,
   admin appointments, T/P cases coming up).
3. Run the composition vote.
4. After the vote, mark the elected members in the same column with
   `Served`, `Chair`, `Alternate`, or `Non-voting`.

That's it. The annual update is two files.

## Institutional workflow (what to ask your IT for)

Universities use different ticketing systems and approval flows. The
sequence below is what we went through at UMass Amherst, generalized so
you can map it to your own institution. Expect this stretch of work to
take one to two weeks of elapsed time, mostly waiting on tickets, not on
active work.

### 9.1 Send the first email to IT

Send a short email to your institution's central IT (or to whichever team
handles Entra ID and enterprise applications). The email should:

- Briefly describe the app (small Python web app for departmental voting,
  stored in your own SharePoint site).
- Ask two questions: (1) can you register an Entra app yourself, or does
  IT do it; (2) is there a departmental Azure subscription you can use
  for hosting, or what infrastructure do they recommend.
- Attach `infra/app_registration.md` and `infra/threat_model.md`.
- Mention requested Graph permissions explicitly: `User.Read` (delegated)
  and `Sites.Selected` (application, scoped to one SharePoint site).

A finished example is in `infra/it_email_draft.md`. CC your department
head and business manager so they are not surprised when downstream
approvals come up.

The key phrase to use is "Sites.Selected, not Sites.ReadWrite.All". IT
security teams approve narrowly-scoped apps quickly; broad scopes trigger
longer reviews.

### 9.2 Expect a reply with two asks

IT will typically respond with two requests of you:

1. **Request an administrative subsidiary account from Account Services
   (or your institution's identity team).** This is a separate elevated
   account that lets you register apps in Azure. Your normal account does
   not have this permission at most universities. The account name often
   has a suffix like `-admin` or `-app` and is created through a form in
   your institution's identity management portal.

2. **Submit an authorization ticket for the app registration.** At UMass
   this is a ServiceNow form titled "Authentication Integration Request
   Form". At other institutions it may be a Jira ticket, a Cherwell form,
   or an email request. The form usually asks about the app's name,
   description, authentication method (pick OIDC, not SAML), intended
   audience, and contact roles (administrative, technical, support).

### 9.3 Get a recharge number from your business manager

If your institution does not have a shared Azure subscription for
departments, the typical path is for IT to create a subscription for your
department that bills back via internal recharge. You will need:

- Your departmental recharge number or chartfield (your business
  manager has this).
- A billing contact (your business manager).
- Approval from your department head if any sign-off is required.

For an app this size, expected hosting cost is roughly $150 to $200 per
year on Azure App Service B1 tier. Cheap, but it still needs a
chartfield.

Loop in your business manager and department head with a short note
explaining the cost and the recharge ask. A draft for this email is at
the end of this section.

### 9.4 Create the app registration yourself

Once your admin subsidiary account is live (often takes 1 to 2 hours to
propagate after creation), follow the steps in section 4 of this document
to create the registration in `portal.azure.com`. Save the Application
(client) ID, Directory (tenant) ID, and Client Secret Value.

### 9.5 Wait for authorization and SharePoint grant

After you submit the authorization ticket (step 9.2) and create the app
registration (step 9.4), IT will:

- Review your security request.
- Authorize the app registration in the tenant.
- Grant the app `Sites.Selected` write permission on your specific
  SharePoint site (the site owner usually has to approve this).

This is the longest wait. Stage progress is typically visible in their
ticketing system.

### 9.6 Confirm and configure

When the authorization ticket completes, fill in `SHAREPOINT_HOSTNAME`
and `SHAREPOINT_SITE_PATH` in your `.env`, swap the storage backend from
local to Graph (small code change, ask your developer or AI assistant),
and deploy.

### Draft note to your business manager and department head

```
Dear [Department Head], [Business Manager],

I have built a small Python web app for our departmental faculty votes
(yes/no motions, approval voting, ranked-choice elections). It runs
inside our existing Microsoft 365 environment, with ballot data stored
in our department's SharePoint site. IT has confirmed they can support
this.

Two things needed to launch:

1. An administrative subsidiary account. I think this is just my ask to
   Account Services, but flagging in case there is a department process.
2. A recharge number for Azure hosting. Expected cost is about $150 to
   $200 per year on Azure App Service.

Alternatively, if our department has a small Linux virtual machine with
spare capacity, we can run it there for free with data still in our
SharePoint site. Either way works, but native Azure would be smoother.

Thanks for your consideration.

Best,
[Your name]
```

## 10. UMass Amherst specifics

If you are adopting this from inside UMass Amherst (another College of
Engineering department, or any other academic unit), follow these
concrete steps. They are the steps we actually walked through, with the
real URLs and forms.

### 10.1 Send the initial email

Send to `it@umass.edu` with subject line:

> Departmental app for [Your unit] faculty voting: Entra registration and hosting question

Body and attachments per `infra/it_email_draft.md`. CC your department
head and business manager. UMass IT typically routes the request
internally within a business day.

### 10.2 What UMass IT will ask of you

You will get a reply describing two next steps:

1. **Request an administrative subsidiary account from Account Services.**
   Log into `spire.umass.edu`, navigate to IT Accounts, and add a
   subsidiary account. Use a descriptive name like `xxx-vote-admin` (your
   NetID prefix plus `-vote-admin`). The form requires:
   - Account name (e.g. `abc-vote-admin`)
   - Alt first name (e.g. "Your Unit Voting"), alt last name ("Admin"),
     and display name (concatenation of the two)
   - Description (50 chars max), e.g. "create and manage an Entra app
     registration"
   - Usage type: Admin
   - Email type: Office365 (Exchange Mail)
   - Leave the email alias placeholder empty
   - Leave Blogs / ServiceNow / VPN / Wireless unchecked
   - Set the password during creation

   The account takes 1 to 2 hours to propagate into Entra after
   creation. Sign-in format is `xxx-vote-admin@umass.edu`. Do not bother
   guessing admin subdomain variants; it is the plain `@umass.edu` form.

2. **Submit a ServiceNow authorization request.** The form is the
   "Authentication Integration Request Form" reachable at
   `https://umass.service-now.com/` under Service Catalog > Accounts &
   Access > Authentication & Identity Access Management. The exact link
   is usually provided in the IT reply.

   Form fields to know:
   - Add new or switch existing SSO method: **Add new**
   - Select authentication method: **Azure AD: oauth** (NOT SAML; OIDC is
     what this app uses)
   - AD/LDAP justification statement: the form requires text here even
     though it does not apply to OIDC. Write "Not applicable. Using
     Azure AD (OAuth/OIDC), not AD/LDAP."
   - Service name: your app name
   - Integration Type: **Local Application managed by UMass**
   - Service description: one or two sentences describing the app
   - InCommon federation: **No**
   - Intended audience: e.g. "AD group of [Your unit] faculty"
   - Authorized user population: e.g. "Faculty in [Your unit]"
   - Roles: sponsoring business unit/director = your DH; administrative
     contact = your business manager (optional); technical and user
     support contact = you
   - SSO Technical Information section: leave most blank, since this is
     OIDC not SAML. Set "Authorization will be handled by: SP" and put
     in Additional comments: "Application uses OIDC via MSAL Python, not
     SAML. Application ID and redirect URI will be provided after the app
     registration is created in portal.azure.com."

   The form is SAML-centric but UMass IT handles OIDC submissions
   regularly. Vendor documentation field can be left blank; you do not
   need to send them Microsoft's own MSAL docs.

### 10.3 Recharge number from your business manager

UMass does not have a shared departmental Azure subscription. Each
department gets its own subscription billed via recharge. Ask your
department's business manager for the recharge number / chartfield and
have them email it (or be ready to send it) to UMass IT.

Recharge cost for App Service B1 tier is roughly $150 to $200 per year
for an app this size.

Alternatively, if your department has a Linux VM with spare capacity, you
can run the app there for free, with ballot data still in SharePoint.

### 10.4 Create the registration in portal.azure.com

Sign into `portal.azure.com` with the new `xxx-vote-admin@umass.edu`
account. Navigate to Microsoft Entra ID > App registrations > New
registration. Fill in:

- Name: your app name (e.g. "MIE Voting App")
- Supported account types: Single tenant only - University of Massachusetts
- Redirect URI: Web, `http://localhost:8000/auth/callback` for development

After creating, capture:
- Application (client) ID (goes into `.env` as `AZURE_CLIENT_ID`)
- Directory (tenant) ID (goes into `.env` as `AZURE_TENANT_ID`)

Then in the registration's sidebar:
- API permissions: add Microsoft Graph **Application** permission
  `Sites.Selected` (User.Read is added by default; do not change that)
- Certificates & secrets: create a client secret, copy the **Value**
  (NOT Secret ID), put in `.env` as `AZURE_CLIENT_SECRET`. Choose 180
  days expiry. Set a calendar reminder to rotate it.

### 10.5 Wait for ServiceNow approval

The ServiceNow ticket progresses through six stages: Information Security
Review, Pending Information Security Approval, LAN Support Notification,
Fulfillment, Request Complete Notification, Completed. You can attach
files to the ticket; doing so for `infra/app_registration.md` and
`infra/threat_model.md` is recommended even if you sent them via email,
since the InfoSec reviewer reads from the ticket.

Once the ticket completes, IT grants `Sites.Selected` write on your
specific SharePoint site (your site owner approves). You fill in
`SHAREPOINT_HOSTNAME` (e.g. `umass.sharepoint.com`) and
`SHAREPOINT_SITE_PATH` (e.g. `/sites/MIE-Faculty`) in `.env`.

### 10.6 Hosting decision

If you go with Azure App Service via the dept recharge subscription, IT
will create the subscription and a resource group for you. From there you
deploy as a normal Python web app. Update the redirect URI in your Entra
registration to your production URL.

If you go with a department VM, set up uvicorn behind nginx or Caddy on
the VM and add its URL as a redirect URI in the registration.

## 11. Publishing this for other departments

The cleanest way to share with other units is a public GitHub repository.
Two practical steps:

1. **Create the repo.** From PowerShell (Windows):

   ```powershell
   cd C:\Users\Dynan\Desktop\MIEVotingApp
   git init
   git add .
   git commit -m "Initial commit"
   gh repo create voting-app --public --source=. --push
   ```

   Or from bash (macOS / Linux):

   ```
   cd ~/path/to/MIEVotingApp
   git init
   git add .
   git commit -m "Initial commit"
   gh repo create voting-app --public --source=. --push
   ```

   The `.gitignore` already excludes the data files (`faculty list.csv`,
   `dpc history*.csv`, `faculty photos/`, `.env`, `data/`). Verify before
   pushing: `git status` should show only code, docs, templates, and
   `config/rules.yaml`. If it shows any of your real personnel data, do
   NOT push.

2. **Mark the repo as a template** in GitHub settings. Other departments
   can then click "Use this template" to get their own copy without
   forking, which is the right semantic for adoption.

Add a clear repository description and topics like `voting`,
`faculty-governance`, `entra-id`, `fastapi`. Link `README.md` from a
short post on your institution's IT mailing list or wherever academic
governance tools get shared. UMass adopters can reach the repo and find
section 10 above ready-made.

Optional: tag a `v1.0` release once you have successfully run a real
vote, so downstream adopters can pin to a known-good version.

## Where to ask for help

For questions about the original implementation: open an issue on the
upstream repository or contact the maintainer.

For institution-specific questions (Entra registration, SharePoint access,
hosting): your local IT department.
