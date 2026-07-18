# AGENTS.md — maintainer guide for Scranton

> Loaded every session. High-signal only. The product definition is
> `Pre-dev/product/RECADRAGE_2026-07-12.md` (**executed in full,
> 2026-07-13** - the app now matches it) with the owner-validated
> mockup `Pre-dev/product/MAQUETTE_2026-07-12.html`. The UX source of
> truth is the pitch deck (`Pre-dev/pitch/scranton_slides_v6.html`),
> not the distilled feature lists — that chain broke once, do not let
> it break again. The *plan* lives in `Pre-dev/product/PRODUCT_ROADMAP.md`;
> the *architecture and data model* in `Pre-dev/product/SCRANTON_CONTEXT.md`;
> per-feature detail in `docs/<feature>.md`. This file is the operating
> manual: rules, invariants, gotchas, commands.

## What Scranton is

A **privacy-first** managerial OS for proximity managers: capture the
human layer (Tell Dwight), recall it in plain language (Ask Pam), feel
the team's mood (Pretzel Day / Meet Toby), summarize and export (Smart
Summaries / Send Angela), hand over cleanly (Transfer to Philly).
Character features are **specialized agents orchestrated by the manager**
- the AI proposes, the human decides. Stack: FastAPI + SQLite
(SQLAlchemy) + ChromaDB + vanilla HTML/CSS/JS, Python 3.12, Mistral via a
provider seam. Backend under `backend/app/`, UI under `frontend/`.

**Doctrine pivot (owner, 2026-07-18): NOT local-first anymore.**
"Ça fait bien longtemps qu'on s'est éloigné du local-first pour passer
au privacy-first" - Scranton is a client-server web app: every person
reaches it from their own machine and logs in (smartphone is the
longer-term future), and connecting the team's existing solutions
(storage, AI, communication, accounting) is core to the thesis. The
MVP deployment is self-hosted on a team machine (documented limit: if
that machine sleeps, Scranton is closed), but the code is written like
a plain web app - HTTPS-ready, config by environment, nothing assumes
localhost - so a hosted instance is a deployment, not a rewrite.

## Non-negotiable rules (from the owner)

1. **Never write code without an explicit "go".** Surface options first.
2. **Never modify the validated data model** (`SCRANTON_CONTEXT.md` §5:
   9 tables + the 3 Darryl tables, session 2026-07-15 + the
   `edited_documents` table, session 2026-07-16 + `users` and
   `sessions`, identity session 2026-07-18) without a dedicated
   session. Mapping it to the ORM is fine; adding/renaming fields is
   not.
3. **Honor the seams** - never hardcode a provider, a data source, a
   vector store, or a character name/avatar. Each lives behind an
   interface or a config map.
4. Code + docstrings in **English**; exchanges with the owner in French.
   Pedagogical comments (**why**, not what) - the repo is a portfolio and
   a learning resource. **No em dash** in code/strings (use `-` or `:`).
   No emoji in UI except the Pretzel Day mood palette. Every function has
   a docstring. Routes are `/api/v1/...`. Conventional commits.
   **UI naming (owner rule, QA v6)**: sentences address the AGENT
   (`agent_name`: "Edit with Dwight", "What should Dwight change?");
   buttons, tabs and titles name the ACTION (`display_name`: "Tell
   Dwight"). Both come from the characters map, never hardcoded.
5. Commit + push at each milestone; the repo stays demo-ready.

## Invariants that break silently if violated

- **Validation is the ONLY gate to memory - and filing a document IS
  the validation.** For the human layer, segments are embedded into
  ChromaDB at *validation* time, never at capture; only `VALIDATED`
  segments feed Ask Pam, Meet Toby, Smart Summaries and Transfer to
  Philly; never index a proposed or rejected segment. For documents,
  the owner's day-one doctrine (reaffirmed 2026-07-15): a document
  placed in the folder shared with Scranton was validated BY that human
  gesture - it feeds Pam directly through agent Darryl (BUILT
  2026-07-15, `docs/darryl.md`); Dwight has no business with it (Dwight
  structures unstructured HUMAN input, nothing else). Removing a file
  from the folder withdraws the consent: soft delete + vectors dropped
  at sync.
- **Identity is a server fact, never a UI state** (identity session,
  2026-07-18). Every route except `/auth/status|setup|login`,
  `/config/ui` and `/health` requires a session cookie; the role
  guards live in `api/deps.py` (`require_manager`, `require_member`)
  and the manager-only perimeter is: Dwight, Toby, Darryl, edited
  documents, handover, Angela, ingest, summary GENERATION, the admin
  surface. Member-self rules are forced server-side: a check-in is
  always your own, a member's mood history is filtered to self, the
  personal profile is writable by its owner ONLY (the
  manager-on-behalf era ended with the POC), the roster is shaped by
  role. The manager is a `users` row WITHOUT a roster row (identity
  apart, owner 2026-07-14) - a future co-admin is a role value, never
  a table move. Passwords are argon2id hashes, session tokens stored
  as SHA-256 only; a provisional password's ONLY exposure is the
  create/reset response (never stored, never logged, never shown
  again) and first login forces its replacement. Deactivating an
  account revokes every session at the same commit. `/auth/setup` is a
  one-time door: it 409s as soon as a manager exists. Deterministic
  signals first (the actual roster matched against folder path and file
  name - no filing convention to configure), LLM second opinion under
  `DARRYL_MIN_CONFIDENCE` (settings, default 0.75), and below the floor
  the UNCLASSIFIED BIN: still queryable, feeds no entity file, fixed in
  one click from the Pam overlay strip (a manager tag REPLACES the
  routing). Spreadsheets are cataloged (name, folder, date, link),
  never content-extracted. Versions: `family_key` groups a file's
  versions, only `is_latest` answers by default, ALL versions through
  the deterministic Pam route ("toutes les versions ..."). **Every
  document title opens the in-app preview** (C2, 2026-07-17: read
  before filing) - the extracted text re-read from `document_chunks`
  (exactly what Pam sees) plus "Open in Drive"; Scranton never renders
  original formats, catalog-only files preview as their catalog card.
- **SQLite is the source of truth for text.** ChromaDB stores vectors +
  *scalar* metadata only. Retrieval returns ids + scores; text is re-read
  from SQLite. A hit whose id is missing from SQLite is skipped, never
  answered from. TWO collections since 2026-07-15: `segments` (human
  layer) and `documents` (corpus, one vector per chunk). The corpus
  collection's metadata is STATIC (`chunk_id`, `document_id`,
  `data_type: cold`): lifecycle rules (deleted docs, silenced older
  versions) apply at the SQLite re-read in Pam, never in the index -
  re-filing a document must never re-embed anything.
- **Chroma metadata is flattened to scalars** (no lists): `team_member_3:
  true`, `view_commitment: true`, plus `data_type`, `sensitivity_level`,
  `entry_id`. Multi-key filters need Chroma's `$and` (handled in
  `chroma.py`).
- **A birthday is a day, never an age.** The year is erased everywhere
  (normalized to `BIRTHDAY_YEAR = 2000`, a leap year), never shown, never
  asked. See `domain/models.py`.
- **Transfer to Philly is verbatim and LLM-free.** A GDPR artifact
  carries exact validated segments. The member-owned profile and mood
  history are NEVER in a handover.
- **A handover is a point-in-time consent.** `handover_validations`
  moves strictly forward (proposed -> employee_reviewed ->
  both_validated -> sent); the selection freezes at review, the fiche
  SHA-256 at signature, and `sent` is an explicit manager action - a
  download never transmits. The signed export re-renders byte-identical
  bytes (generated_at pinned to validated_at): keep it deterministic.
- **People are never scored** (the north star). `MOOD_INDEX` indexes the
  mood, never the person. Team-level averages are fine; ranking or rating
  a human is off-thesis. Toby signals and the annual-review template are
  *material for discussion*, never verdicts. Generated documents describe
  moods in WORDS - never an average or index that reads like a score.
- **People information never flows through Pam** (owner, QA 2026-07-14).
  Pam's Q&A retrieval is COLD-ONLY (`data_type` filter) and her template
  router serves clients/projects only, generated `cold_only=True`. A
  broad question naming ONE member gets a deterministic redirect (Toby /
  the Desk); naming TWO members gets the deterministic shared
  projects/clients answer (validated tags, cold sources, no LLM). The
  warm layer lives in Meet Toby and Michael's Desk briefs (manager-only
  surfaces, full warm+cold mix). Personal-life data is member-DECLARED
  through their own Pretzel Day space: Dwight leaves such info out of
  manager notes and SAYS so (`privacy_note`, prompt rule 5) - an
  acknowledgment, never a suggestion flow.
- **Pam's sources are the cited ones.** Retrieval hits below
  `PAM_MIN_SCORE` (settings, default 0.6 - a tuning lever like
  LLM_MODEL) never reach the model; after the answer, only excerpts it
  cites [n] are returned, keeping their excerpt number (`ref`). An
  answer with no citation shows no sources. Recomputing source numbers
  positionally in the UI would desync the citations - use `ref`.
- **Celebrations are PAUSED** (owner, QA 2 2026-07-14): `CELEBRATIONS =
  false` in `frontend/app.js` disables TWSS and the whole Maire surface
  (popin, ritual card, fetch). Backend endpoints stay live. Do not
  re-enable without the celebrations session (BACKLOG).
- **Structured LLM calls go through `services/llm_json.complete_validated`**
  (parse tolerant of ```json fences, Pydantic validate, one retry). Used
  by Dwight and Summaries. Don't re-roll a bespoke parser.
- **Smart Summary templates are DATA** (`TEMPLATES` registry in
  `summary_service.py`). Gathering is **exhaustive SQL over tags, not
  vector top-k** (a file wants everything; search would truncate). A new
  template is a registry entry, not a code path.
- **An edited document never changes on its own** (editing session
  2026-07-16, surface redesigned C3 2026-07-17,
  `docs/document_editing.md`). Templates stay living; the document is
  born at its first Save (`edited_documents`, last state only) - "Edit"
  opens a DRAFT and persists nothing. The editor is ONE full-frame
  canvas: every gesture (Dwight revision, manual Apply, weave) APPLIES
  to the canvas highlighted vs version n-1, "Undo last edit" steps
  back one gesture (session-scoped stack, survives Save), Save is the
  only persisting gesture, unsaved work is guarded (in-app +
  beforeunload). Every diff is difflib-COMPUTED, never self-reported -
  manual edits ask `POST /documents/diff`, Dwight revises the CANVAS
  (content_md override) as a PURE reviser (zero memory access). The
  memory's movement is PRESENTED as delta proposals (segments newer
  than `memory_reviewed_at`), never applied. A Desk generate button
  whose template + target is already saved REOPENS the saved document
  (owner, QA v6) - never a fresh generation ignoring the edits. Saving
  a client/project document files it into Darryl's corpus (source
  `scranton`, manager tag 1.0); **person-targeted documents never
  enter the corpus** (people never flow through Pam). Darryl's sync
  excludes `source='scranton'` rows - removing that filter would
  soft-delete every saved document. The engine (`editing_service.py`)
  is surface-independent: Oscar consumes it next.
- **Entity routing is closed-world**: Dwight may only tag entities from
  the roster injected into its prompt. Unknown names are dropped.

## The seams

`LLMProvider` (mistral/gemini/ollama) · `IngestionSource` (local/gdrive,
the Dwight gate) · `DocumentSource` (local/gdrive, Darryl's corpus -
Notion/Teams/Slack/GMail plug in here later) · `ContentExtractor`
(registry per MIME type; spreadsheets deliberately absent) ·
`VectorStore` (chroma, two collections) · `Transcriber` (V2 voice) ·
`Exporter` (md/html) · `characters` config map (agent registry +
IP-safe rebrand; `darryl` has no avatar yet, and the seed member is
Val so the agent owns the name).
Services are pure logic and take seams via `api/deps.py`; adapters do the
I/O. The lifespan hook (`main.py`) builds shared adapters once onto
`app.state`; deps only assemble - which is why tests swap any seam via
`app.dependency_overrides`.

## Gotchas (real ones, hit during the build)

- **mistralai 2.x**: import is `from mistralai.client import Mistral` (not
  the 1.x `from mistralai import Mistral`).
- **opentelemetry version conflict** between chromadb 1.5.9 and mistralai
  2.5.2 is reported by pip but both import fine. Re-check on any bump.
- **Preview/dev server runs WITHOUT `--reload`**: after a *backend*
  change you must restart it (frontend changes just need a page reload).
- **Empty repeated query params vanish on the wire** - HTTP can't send
  `[]`. Handover uses ONE comma-separated param so "disclose nothing"
  stays expressible (`include_warm=` or `=none`).
- **SQLite stores naive datetimes**: compare with naive UTC via
  `mood_service.utc_cutoff`, never with aware datetimes.
- **Frontend**: fetch character names/avatars from `/api/v1/config/ui`
  (never hardcode); always `esc()` model/user text before `innerHTML`;
  containers that survive view switches need `onclick` (not
  `addEventListener` - it accumulates) and lose their `placeholder`
  class on first render (done in `show()`); author `display` on a
  `[hidden]` element defeats it - restate `#x[hidden] {display:none}`.
- **Answer language is PINNED server-side** (tuning pass 2026-07-09):
  `services/language.py` detects French/English and injects an explicit
  language line into every Dwight/Pam/Summary user message. Never rely
  on "answer in the language of X" prompt wording alone - it drifts on
  rerolls. mistral-small still cannot calibrate confidence finely
  (narrow 0.8-0.9 band; medium spreads 0.7-1.0 and is stable); it also
  invents birth years (guarded by year-erasure).
- **`LLM_MODEL` in .env overrides the chat model** (e.g.
  `mistral-medium-latest`) without touching code - the A/B lever.
- Dev DB may hold ad-hoc test rows (e.g. Kevin/Thomas birthdays set
  during verification). Run the seed with `--reset` for a clean demo.
- **The app is behind a login since the identity session**: the seed
  prints the demo credentials (michael@dundermifflin.com /
  worldsbestboss + one member account per roster name, pretzelday). A
  FRESH database shows the first-run setup, not the login. In tests,
  the `client` fixture is already logged in as the manager;
  `anon_client` has no session and `member_login()` returns a
  logged-in member client - never re-implement login in a test.
- **The framework Python is universal (arm64+x86_64), the venv wheels
  are arm64-only**: a Rosetta launch context kills the server at import
  time (pydantic_core dlopen). Both launchers force the slice via
  `/usr/bin/arch -arm64 <venv-python> -m ...` - never remove it, and
  spawn long-lived processes the same way.

## Commands

```bash
source .venv/bin/activate                      # Python 3.12
pytest                                          # offline suite (no key needed)
pytest -m integration                           # real Mistral (needs MISTRAL_API_KEY)
uvicorn backend.app.main:app --reload --port 8001   # 8000 is another project
python -m backend.app.db.seed --reset           # Dunder Mifflin demo dataset
open "Scranton QA.command"                      # owner QA: throwaway env (data/qa/)
                                                # on :8010 + /qa.html checklist
```

Tests never hit the network: `tests/conftest.py` provides
`ScriptedLLMProvider` (scripts model answers) and `FakeVectorStore`
(scripts hits / records upserts). Real-provider calls live behind the
`integration` marker (excluded by default). Frontend: vanilla JS served
statically by the same process; `Scranton.app` at the repo root is the
Dock launcher (must stay in the repo).

## Provisional decisions (confirm with the owner before building on them)

- `personal_profile` is free text (structured table stayed open).
- Dwight's profile extraction is systematic-but-consensual (on-demand
  stayed open).

## Current state (July 2026)

**RECADRAGE EXECUTED IN FULL (2026-07-13), FOUR owner QA passes done
(QA 1/2 2026-07-14: 35/37 + lot A, 36/37 + lot B; QA v5 2026-07-16
and v6 2026-07-18: lots C1-C4, sliding-scope checklists).**
The app IS the recadrage now: one OS, two roles (manager: Dashboard /
Michael's Desk / Meet Toby / Admin; member: My board / Pretzel Day -
the role comes from the LOGIN since the identity session, the old
picker is gone), Dwight and Pam as floating overlay actions, Pam serving
Client/Project templates on broad questions, Toby speaking in dated
quotes, human tags with spelled-out confidence. Build on this UI.
Lot B (QA 2): Pam noise fixed (score floor + cited-only sources),
people redirect + two-member shared-work answers, Dwight privacy
acknowledgment, celebrations paused, weak-signals card links to Toby,
seed enriched (cold Ryan, validated Prince Family Paper, Ryan+Kelly
shared client).

**THE ROADMAP WAS REBUILT WITH THE OWNER (2026-07-15)** - see
`PRODUCT_ROADMAP.md` section 4, four tiers (indispensable / nécessaire /
utile / agréable). **DARRYL L'ARCHIVISTE SHIPPED the same day** (the
full session: data model, pipeline, one Pam over two badged memories
with clickable links, the archive strip in the Pam overlay, seed demo
corpus, owner arbitrations recorded in BACKLOG). Reference:
`docs/darryl.md`. **DOCUMENT EDITING SHIPPED 2026-07-16** (the full
session: `edited_documents` table, surface-independent engine, delta
proposals, pure-reviser Dwight with computed diff, person exception,
Pam-overlay history strip, first real-Drive sync - owner arbitrations
in BACKLOG, reference `docs/document_editing.md`).

**QA v5/v6 CYCLE DONE (2026-07-16 -> 18, lots C1-C4, 170 tests).**
The owner's v5 verdict killed the first editing surface ("unusable
from the second edit"); the engine stayed, the surface was rebuilt on
his arbitrations (C3: one full-frame canvas, Save/Edit split, apply +
undo, save-only persistence - see the invariant above). Around it:
the Dwight thread keeps the manager's note visible, sticky overlay
inputs, "Clear panel content", one Show more + fold accordion per
memory in the Pam strip, the document preview (C2), the agent/action
naming rule wired as `agent_name` (C4), a saved generation reopening
as the manager's document, and the demo corpus enriched to twelve
documents (three titles are QA anchors - flagged in seed.py, never
rename them). QA v6: 19/22, only the real-Drive section left untested.
The QA checklist (`frontend/qa.html`) is v7 (identity session +
real-Drive section) and matches the product.

**IDENTITY/ADMIN SESSION SHIPPED (2026-07-18, the full session,
lots 1-4, 196 tests).** The privacy-first pivot was arbitrated at its
opening (see "What Scranton is") along with: login per profile,
provisional password + forced first change (no mail infra), unified
`users` table (+ `sessions`), email as the ONLY roster contact field,
30-day sessions with logout, seed creates the demo accounts. Shipped:
the two tables, argon2id auth behind `/api/v1/auth`, the whole
server-side scoping (see the identity invariant), the landing + login
worded from the deck's cover, the Admin view (create / edit /
deactivate / reactivate / reset password, one-time password display),
the manager eligible Maire (birthday on his users row; surfaces when
celebrations return). The POC role switch and identity picker are
GONE - the session IS the identity. Owner arbitrations recorded in
BACKLOG; reference `docs/identity.md`. Deferred: co-admin (a role
value away), HTTPS/hosted deployment, member capture (V2). **NEXT:
owner QA v7 (`frontend/qa.html`), then Oscar and exports & partage;
celebrations overhaul stays the agréable tier (TWSS and Maire off
until then).**

**Succession (2026-07-12)**: the owner passed the baton from Fable to
Opus; the former "pure Fable repo" rule is lifted - build ON this
base, do not rebuild it. The six-hats working method applies (PM /
architect / designer / developer / QA / Fabrice the field tester -
see the memory files). Exchanges with the owner stay in French; he is
a product manager learning Python, so keep explaining the why.

History: MVP + MLP shipped; V1 was feature-complete before the
recadrage: **human profile**, **Maire de Scranton**, **Smart
Summaries**, **Send Angela**, and **Transfer to Philly** (dossier +
selective disclosure + signable fiche + the `handover_validations`
consent trail, data model session held 2026-07-08) - the engines stay,
their surfaces move per the recadrage. Also noteworthy:

1. **Tuning pass DONE (2026-07-09, session with the owner)**: language
   pinned server-side (`services/language.py`), light personas for Pam
   and Dwight's clarifications (grounding untouched), calibrated
   confidence scale + hard cap in the Dwight prompt, TWSS duration now
   reading-time based. A/B verdict: small stays acceptable; medium is
   measurably better on confidence calibration and segmentation
   (`LLM_MODEL=mistral-medium-latest` to switch, owner's call - taken:
   medium is active in the owner's .env). Local sovereignty path probed
   (2026-07-09): `OllamaProvider` ships behind the seam, but mistral 7B
   on the owner's M4 16GB is below the bar (broken routing, 88s/note,
   ignores the language pin) - self-hosting waits for a bigger local
   model, it is a V2 topic, not a regression to chase.
2. **GDrive end-to-end run**: wired and tested on mocks, needs the
   owner's one-time OAuth setup (`docs/google_drive_ingestion.md`).
3. Backlog candidates: Pam's Front Page, mood-adaptive TWSS, festive
   Maire (owner wants "plus festif" - custom background or similar),
   and the Pretzel Day icon the owner will provide.

Milestone history and rationale: `git log` and the memory files under
`~/.claude/.../memory/`. Update this file when an invariant or a rule
changes - it is the operating manual of record.
