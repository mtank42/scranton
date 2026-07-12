# CLAUDE.md — maintainer guide for Scranton

> Loaded every session. High-signal only. **READ FIRST:
> `Pre-dev/product/RECADRAGE_2026-07-12.md`** — the owner's product
> realignment (QA verdict): it OVERRIDES SCRANTON_CONTEXT §3 and the
> current UI. The UX source of truth is the pitch deck
> (`Pre-dev/pitch/scranton_slides_v6.html`), not the distilled feature
> lists — that chain broke once, do not let it break again. The *plan*
> lives in `Pre-dev/product/PRODUCT_ROADMAP.md`; the *architecture and
> data model* in `Pre-dev/product/SCRANTON_CONTEXT.md`; per-feature
> detail in `docs/<feature>.md`. This file is the operating manual:
> rules, invariants, gotchas, commands.

## What Scranton is

A local-first managerial OS for proximity managers: capture the human
layer (Tell Dwight), recall it in plain language (Ask Pam), feel the
team's mood (Pretzel Day / Meet Toby), summarize and export (Smart
Summaries / Send Angela), hand over cleanly (Transfer to Philly).
Character features are **specialized agents orchestrated by the manager**
- the AI proposes, the human decides. Stack: FastAPI + SQLite
(SQLAlchemy) + ChromaDB + vanilla HTML/CSS/JS, Python 3.12, Mistral via a
provider seam. Backend under `backend/app/`, UI under `frontend/`.

## Non-negotiable rules (from the owner)

1. **Never write code without an explicit "go".** Surface options first.
2. **Never modify the validated data model** (`SCRANTON_CONTEXT.md` §5:
   9 tables) without a dedicated session. Mapping it to the ORM is fine;
   adding/renaming fields is not.
3. **Honor the seams** - never hardcode a provider, a data source, a
   vector store, or a character name/avatar. Each lives behind an
   interface or a config map.
4. Code + docstrings in **English**; exchanges with the owner in French.
   Pedagogical comments (**why**, not what) - the repo is a portfolio and
   a learning resource. **No em dash** in code/strings (use `-` or `:`).
   No emoji in UI except the Pretzel Day mood palette. Every function has
   a docstring. Routes are `/api/v1/...`. Conventional commits.
5. Commit + push at each milestone; the repo stays demo-ready.

## Invariants that break silently if violated

- **Validation is the ONLY gate to memory.** Segments are embedded into
  ChromaDB at *validation* time, never at capture. Only `VALIDATED`
  segments feed Ask Pam, Meet Toby, Smart Summaries and Transfer to
  Philly. Never index a proposed or rejected segment.
- **SQLite is the source of truth for text.** ChromaDB stores vectors +
  *scalar* metadata only. Retrieval returns ids + scores; text is re-read
  from SQLite. A hit whose id is missing from SQLite is skipped, never
  answered from.
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
  *material for discussion*, never verdicts.
- **Structured LLM calls go through `services/llm_json.complete_validated`**
  (parse tolerant of ```json fences, Pydantic validate, one retry). Used
  by Dwight and Summaries. Don't re-roll a bespoke parser.
- **Smart Summary templates are DATA** (`TEMPLATES` registry in
  `summary_service.py`). Gathering is **exhaustive SQL over tags, not
  vector top-k** (a file wants everything; search would truncate). A new
  template is a registry entry, not a code path.
- **Entity routing is closed-world**: Dwight may only tag entities from
  the roster injected into its prompt. Unknown names are dropped.

## The seams

`LLMProvider` (mistral/gemini/ollama) · `IngestionSource` (local/gdrive) ·
`VectorStore` (chroma) · `Transcriber` (V2 voice) · `Exporter`
(md/html) · `characters` config map (agent registry + IP-safe rebrand).
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

**PRODUCT RECADRAGE PENDING — do not build features on the current UI.**
First QA pass (2026-07-12): the engine holds, the screen architecture
does not — the owner does not recognize his product. Everything to
execute is in `Pre-dev/product/RECADRAGE_2026-07-12.md` (5 role-based
views, Summaries become Pam response templates, Team view dies,
Pretzel Day becomes each member's own space, per-proxy data entry
abolished). Start there.

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
