# Notes for an AI assistant helping a new department adopt this app

If you are an AI assistant being asked to help a new department deploy
this voting app, read this first. It maps the codebase, calls out the
customization points, and lists the gotchas that tripped us up during the
original build so you do not re-discover them.

## Architecture in one paragraph

FastAPI app. Identity comes from Microsoft Entra ID via MSAL Python
(OIDC, authorization code flow). Ballots are stored locally as JSON files
during development, swapped to SharePoint via Microsoft Graph for
production. A faculty registry loads names and ranks from a CSV and
fuzzy-matches photos by filename token overlap. A per-AY status sheet
provides eligibility filtering (hard excludes) and history badges.
Election templates are presets. Ballot anonymity rests on a two-store
separation: voter receipts are HMACs keyed by a per-election salt, ballots
themselves carry no voter identifier. See `infra/threat_model.md`.

## Customization points, in priority order

1. **`config/rules.yaml`**: branding (color, app name), AY column labels,
   status catalog (codes, labels, hard-exclude flags, aliases), name
   aliases, election templates. Touch this first.
2. **`faculty list.csv`**: names and ranks. Replace with the adopting
   department's roster.
3. **`faculty status.csv`** (or any `dpc history*.csv`): per-AY status
   records. Replace.
4. **`faculty photos/`**: photo files. Naming is forgiving; the matcher
   in `app/faculty.py` pairs by token overlap.
5. **`.env`**: Entra IDs and session secret. From the new department's
   own Entra app registration.

## What rarely needs to change

- Ballot logic (`app/ballots/*.py`). IRV, approval, yes/no are
  general-purpose.
- Storage abstraction (`app/storage.py`). The local backend works as-is;
  the SharePoint backend is identical interface, just different writes.
- Anonymity layer (`app/anonymity.py`). HMAC-based receipts are the same
  for any department.
- Photo matcher (`app/faculty.py:_match_photos`). Fuzzy match handles most
  naming conventions; edge cases get fallback initials bubbles.

## Gotchas we hit

1. **Starlette `TemplateResponse` signature**: newer Starlette puts
   `request` first. Easy to miss in older tutorials. All call sites in
   `app/main.py` already use the correct form.

2. **CSV encoding**: faculty lists often have unicode names. The CSV
   loader uses `utf-8-sig` to tolerate BOMs.

3. **Pydantic Settings default capture**: do not put module-level
   constants as default arguments if you want monkeypatching to work in
   tests. Resolve at call time. See `app/faculty_status.py:load_sheet`.

4. **Headerless status sheets**: many departments will hand you an Excel
   they exported from a manual tracking workflow with no header row. The
   loader auto-detects and falls back to `ay_columns` from
   `config/rules.yaml` for the column labels.

5. **Excel locks files on Windows**: when editing the status CSV during
   testing, close Excel before letting code write to it.

6. **Photo matcher false positives**: exact token matches dominate
   substring matches. If a department has names like Chait/Chaitra in the
   same roster, exact-match wins. Watch the startup print of the photo
   match table to confirm.

7. **Untenured override**: only set when the cell in the untenured marker
   column has explicit text. Blank cells must leave rank-based
   classification untouched, otherwise Assistant Professors with blank
   markers get incorrectly flipped to tenured.

8. **The `Sites.Selected` permission**: this is what makes Entra
   registration easy at most institutions. Do not request
   `Sites.ReadWrite.All`; that triggers long security reviews.

9. **CSS color theming**: a single `--umass-red` hex propagates to all
   derived shades via `color-mix()`. Modern browsers only; do not try to
   support legacy IE.

10. **Dev mode bypass**: `MIE_DEV_AUTH=1` in the shell env lets you sign
    in as any name/oid without Entra. Use it for initial UI testing
    before the Entra registration is ready. Never set it in production.

## A reasonable plan for adopting at a new department

1. Read `ADOPTION.md` end to end.
2. Get the new department to send you their faculty list, status sheet
   (if they have one), and brand color.
3. Edit `config/rules.yaml` to match.
4. Drop in their data files.
5. Run locally with `MIE_DEV_AUTH=1` and walk through every ballot type
   to verify the customizations look right.
6. Help them through the Entra registration process at their institution.
7. Fill in `.env` from their registration.
8. Sign in with a real institutional account once and confirm.
9. Discuss hosting with their IT (Azure App Service or dept VM).
10. Hand off.

## When the user asks for new ballot mechanisms

The existing types (yes/no, approval, ranked) cover most academic
governance needs. Before adding a new mechanism, push back and ask if
their use case can be expressed with what already exists. New ballot
types require validate/serialize/tally functions, a template entry,
a Jinja partial, and JS handler. About 100 lines for a simple one.

## When the user asks for cooldown / rotation rules

We deliberately did not encode cooldowns or rotation rules. The
department's preference at MIE was that conventions stay informal and
voters self-regulate, with the history panel providing transparency.
Other departments may differ. If a department wants strict rotation, add
a new hard-exclude rule that checks "served in the immediately prior AY,
except for chair". See discussion in the original development log.

## When the user asks to remove the anonymity guarantee

Do not. The whole point is anonymous ballots. If they want
attributed votes for some specific use case, they can use Microsoft Forms
or a SharePoint List. This app exists for the anonymous case.
