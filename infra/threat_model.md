# Threat Model: MIE Voting App

One-page summary of who we're defending against, what we're protecting,
and how the design holds up. Intended for UMass IT security review and for
faculty who want to verify the anonymity claim before trusting the system.

## What we protect

1. **Ballot secrecy.** For secret ballots, no one (including the app
   operator, IT, or a curious colleague with SharePoint access) should be
   able to link a stored ballot to the faculty member who cast it.
2. **Vote integrity.** Only eligible faculty can vote. Each faculty member
   votes at most once per election. Ballots cannot be modified after
   submission.
3. **Result integrity.** Tallies are reproducible from stored ballots and
   cannot be silently altered.

## Who we defend against

| Adversary                        | In scope? | Notes                                   |
|----------------------------------|-----------|-----------------------------------------|
| Curious colleague                | Yes       | Has UMass SSO, maybe SharePoint access. |
| Departmental staff / chair       | Yes       | May have site-admin rights.             |
| App operator (the developer)     | Partial   | Has server access during elections.     |
| UMass IT with full tenant access | No        | Out of scope; trusted by policy.        |
| External attacker                | Yes       | Defended by Entra ID + UMass network.   |
| Nation-state                     | No        | Not a realistic threat for this use.    |

## Design

### Two-store separation

- **Voter receipts:** `voters/<election_id>/<hmac(oid, election_salt)>`
  records *that* a faculty member voted. Contains no ballot content.
- **Ballots:** `ballots/<election_id>/<random_uuid>.json` contains the
  ballot. Contains no voter identifier.

The app writes to these two stores in separate Graph calls and does not
log the pairing. The `election_salt` is generated when the election is
created and stored with the election metadata; it is the same for all
voters in one election (so receipts can be checked for duplicates) but
different across elections (so cross-election correlation is hard).

### Two auth flows

- **Delegated** (user sign-in) is used only to confirm identity. The
  delegated token never touches SharePoint.
- **App-only** (client credentials) is used for all ballot reads/writes.
  The app's permission is `Sites.Selected`, scoped to one SharePoint site.

This means a faculty member's account being compromised does not, by
itself, leak ballot contents. The attacker would need server-side access
to the app's client secret.

## Known limitations

1. **Timing correlation.** An attacker with real-time access to both
   stores during a live election could correlate writes by timestamp. We
   mitigate this by (a) buffering ballot writes with a random delay
   (planned), and (b) shuffling ballot order at tally time. A determined
   attacker with sub-second log access can still correlate; for very
   sensitive votes (e.g. tenure cases), document this limitation to voters.

2. **Server compromise.** If the host running the app is fully
   compromised during an election, in-memory state could link voters to
   ballots. Mitigation: keep the host minimal, restrict SSH, log
   administrative access.

3. **Operator trust.** The app developer (currently one faculty member)
   has the client secret. Mitigation: rotate secrets after each
   significant election; consider moving the secret to a UMass-managed
   Key Vault if/when the app is hosted by IT.

4. **No cryptographic ballot verification.** This is not an end-to-end
   verifiable voting system (e.g., Helios). Faculty trust rests on the
   design above plus code review, not on a cryptographic proof. For the
   department's use case (low-stakes vs. national elections, all voters
   know each other) this is judged acceptable.

## Out of scope (intentionally)

- Coercion resistance (a faculty member being forced to vote a certain
  way and prove it). Standard for university-internal voting.
- Post-quantum cryptography.
- Voting from outside the UMass tenant.
