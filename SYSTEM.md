# RocketRush NDA System — SYSTEM.md

Sister system to `rr-proposals`. Every NDA is a signable web page. The client uploads a
signature, and anyone can download the signed agreement as a PDF.

**Rocket Rush is always the Receiving Party.** The client is always the Disclosing Party.
(That is why clients sign our NDA: we never disclose the client's name.)

## Repository
- Owner: teamrocketrush-ui
- Repo: rr-ndas
- GitHub Pages: https://teamrocketrush-ui.github.io/rr-ndas

## File Structure
```
rr-ndas/
├── template.html          <- Master NDA (25 clauses, signing + PDF logic) with {{VARIABLES}}
├── ndas.json              <- Registry of all NDAs (what "Hey" lists)
├── scripts/generate.py    <- Fills the template, writes ndas/{key}.html, updates ndas.json
├── tests/test_generate.py <- Unit tests (python3 -I -m unittest discover -s tests)
├── SYSTEM.md              <- This file
├── CLAUDE.md              <- Points sessions here
└── ndas/{client-key}.html <- One page per client NDA
```

## THE CHAT WORKFLOW (follow this exactly)

### When the user says "Hey" (or "hi", "hello", "ndas")
1. Read `ndas.json`.
2. Show the existing NDAs as a numbered list: client, execution date, link. Newest last.
   Signed status: if the network allows, `GET` the public Firestore record for each NDA (see
   "Checking signed status") and show ✅ Signed / ⏳ Awaiting signature. If that read is blocked,
   say the status is not checked and show the link only. Never guess a status.
3. End with: `Reply "new" to create an NDA, or a number to open / download / delete one.`

### When the user says "new"
Ask the questions **one at a time, back to back**. Wait for each answer.
Clients are either a **company** or an **individual** signing in their own name. If the user gives a
person's name (or says the NDA is in the client's name), use `--type individual`; otherwise company.
1. Client company full legal name? (individual: the person's full name)
2. Client registered office address? (individual: residential address)
3. Client GST number? (or N/A; usually N/A for an individual)
4. Client signatory name? (company only; default "Authorised Signatory". Skip for an individual.)
5. Purpose of the engagement? (e.g. "LinkedIn Personal Branding")
6. Execution date and place? (default: today, Mathura)

Then show a short summary and ask the user to confirm. On confirmation:
1. Run `python3 scripts/generate.py [--type individual] --company ... --address ... --gst ... --signatory ... --purpose ... [--date ...] [--place ...]`
   (for an individual, `--company` carries the person's name and `--signatory` is not needed)
2. Run the tests: `python3 -I -m unittest discover -s tests`
3. Commit `ndas/{key}.html` and `ndas.json`, push to `main`.
4. Reply with the link `https://teamrocketrush-ui.github.io/rr-ndas/ndas/{key}.html`.
   Pages takes 1–2 minutes to publish. The same link downloads the PDF (Download PDF button).

Pass `--private-suffix` when the user wants a link that cannot be guessed from the company name.

### When the user picks a number
- **Open / download**: give the link. The PDF button is on the page itself.
- **Delete**: do the full cleanup below, after confirming.

## Fixed content (never ask for these)
| Item | Value |
|---|---|
| Default place of execution | Mathura (`DEFAULT_PLACE` in `scripts/generate.py`) |
| Receiving Party | Rocket Rush Partners, A-23, NAVADA, PRAGATI KUNJ, ANAND VAN PHASE 2, Aduki, PO, DIST: Mathura, Uttar Pradesh - 281006 (defined once in `scripts/generate.py` as `RR_ADDRESS`, `RR_GST`, `RR_PAN`; used by every NDA) |
| RR GST / PAN | 09ABLFR1598J1ZG / ABLFR1598J |
| RR signatory | Nikhil Mishra (signature image is embedded in the template) |
| Term | Confidentiality for 5 years from termination |
| Governing law | India |
| Security-incident notice | 1 business day |

## Changing Rocket Rush's own details
Edit `RR_ADDRESS`, `RR_GST` or `RR_PAN` in `scripts/generate.py`. New NDAs pick it up automatically.
To update an NDA that already exists, run `python3 scripts/generate.py --regenerate {client-key}`.
Do not regenerate an NDA that has already been signed or dated in the past without the user's say-so:
it would change the text the client agreed to. (Cautilya, executed 22 May 2026, keeps the original Noida address.)

## Template Variables
| Variable | Description |
|---|---|
| CLIENT_COMPANY | Client company full name |
| CLIENT_ADDRESS | Client registered office |
| CLIENT_GST_ROW_HTML / CLIENT_GST_SENTENCE | Built from `--gst`; omitted when GST is N/A |
| CLIENT_SIGNATORY | Client signatory name |
| PURPOSE | The "Proposed Transaction" |
| EXEC_DATE / EXEC_PLACE | Execution date and place |
| *_JS variants | Same values as safe JavaScript strings. All values are escaped by `generate.py` |

## Client Key Format
Lowercase company name, legal suffixes dropped (pvt, ltd, private, limited, llp, inc…), spaces to hyphens.
- "Cautilya Wealth and Education Pvt Ltd." → `cautilya-wealth-and-education`
- If the key exists already: `-2`, `-3`, …

## NDA URL Pattern
https://teamrocketrush-ui.github.io/rr-ndas/ndas/{client-key}.html

## Tech Stack (shared with the proposal system, nothing new to set up)
| Layer | Service | Purpose |
|---|---|---|
| Hosting | GitHub Pages | Serves the NDA pages |
| Signed state | Firebase Firestore (project `rocketrush-proposals`) | Signed state on every device |
| Signature images | Cloudinary (cloud `dsjpiafaa`, preset `rocketrush_signatures`) | Permanent signature storage |
| Notifications | Formspree (same form as proposals) | Emails the team when an NDA is signed. Subject: "NDA signed — {company}" |
| PDF | Browser print engine + A4 print stylesheet | Real selectable text, sharp signatures, page numbers |

### Where NDA data lives
- Firestore: collection `signatures`, document ID `nda-{client-key}` (the `nda-` prefix keeps NDAs apart
  from proposals, which use the bare key, and needs no new Firestore rules).
  Fields: signed, type ("nda"), date, sigUrl, client, signatory, nda, timestamp.
- Cloudinary: folder `nda-signatures/{client-key}/`, public ID `{client-key}_client_sig`.
- To give NDAs their own collection later, change the single constant `FS_COLLECTION` in `template.html`
  (and update Firestore rules to allow it).

### Checking signed status
`GET https://firestore.googleapis.com/v1/projects/rocketrush-proposals/databases/(default)/documents/signatures/nda-{client-key}`
returns the record if signed and 404 if not. This is the same public read the NDA page makes itself.

## PDF download
The **Download PDF** button (top bar, and again after signing) opens the browser's print dialog with an
A4 layout: every clause expanded, both signatures, page numbers, file name "NDA - Rocket Rush x {Client}".
The user chooses **Save as PDF**. In Chrome, untick "Headers and footers" for the cleanest result.

## ndas.json Structure
```json
[
  {
    "id": "cautilya-wealth-and-education",
    "client_name": "Cautilya Wealth and Education Pvt Ltd.",
    "signatory": "Authorised Signatory",
    "gst": "29AAMCC5686K1ZT",
    "address": "…",
    "purpose": "LinkedIn Personal Branding",
    "exec_date": "22nd May 2026",
    "exec_place": "Noida",
    "created_date": "12 November 2026",
    "url": "https://teamrocketrush-ui.github.io/rr-ndas/ndas/cautilya-wealth-and-education.html"
  }
]
```

## Delete NDA — Full Cleanup (always do all 4)
1. Delete the page from GitHub: `ndas/{client-key}.html`
2. Remove its entry from `ndas.json`
3. Delete the Firestore document: collection=`signatures`, doc=`nda-{client-key}`
4. Delete the Cloudinary image: public_id=`nda-signatures/{client-key}/{client-key}_client_sig`

## Privacy note
The NDA pages and `ndas.json` contain client names and addresses. If this repo is public, anyone who
finds the repo can read them, and `template.html` already carries `noindex` so search engines skip the pages.
Keep the repo private if the plan supports Pages on private repos, or use `--private-suffix` links.

## Individual clients
`template.html` holds two variants of three passages, selected by `<!--IF:company-->…<!--/IF-->` and
`<!--IF:individual-->…<!--/IF-->` blocks: the opening party description ("residing at" instead of
"with its Registered Office at"), the signature title ("Disclosing Party" instead of "Authorised Signatory — {company}"),
and clause 20 (Authority). The individual clause 20 wording was approved by the user on 12 Nov 2026 and should
be reviewed by a lawyer. Every other clause is identical for both types.

## Custom clauses (per-NDA changes)
When a client asks for wording changes, do **not** edit `template.html`. Put the changes in `custom/{client-key}.json`:
```json
{
  "confidentiality_period": "text for the summary table (optional)",
  "edits":   [{"clause": 18, "find": "exact existing text", "replace": "new text"}],
  "append":  [{"clause": 8, "paragraphs": ["extra paragraph added to the end of clause 8"]}],
  "new_clauses": [{"title": "Use of AI Tools", "paragraphs": ["clause 26 text"]}]
}
```
Each `find` must match exactly once inside that clause, or generation stops with an error. New clauses are numbered
from 26 and the heading ("Clauses 1 – N") updates itself. Apply with `python3 scripts/generate.py --regenerate {client-key}`.
Always show the user the exact wording and get approval before pushing to `main`. Only change an NDA that has not
been signed. If it was signed, make a new NDA or an amendment instead. A test fails if a committed page is out of sync
with its custom file.
Current custom NDAs: `rajnish-kumar` (AI tools, no reuse, ownership, private material, third-party access,
term, deletion trigger, notices, Mathura jurisdiction).

## Clause numbering
The original document restarted numbering partway (1–7, then 2–19). `template.html` numbers the 25 clauses
1–25 in the original order with the original wording, plus typo fixes only. One heading was renamed:
clause 9 "Return or Destruction of Information" (was "No Obligation of Confidentiality").
Known items left as they were in the source: governing law appears in clauses 17 and 18, entire agreement
appears in clauses 17 and 22, and "Engagement Schedule" in clause 7 is not defined anywhere.
