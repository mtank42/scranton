# SCRANTON — ARCHITECTURE SKETCH (ébauche)
> A **draft blueprint**, not a final design. Purpose: give a strong LLM agent (Fable 5) a starting shape to refine and then code.
> Pairs with `PRODUCT_ROADMAP.md` (what/when) and `SCRANTON_CONTEXT.md` (data model, stack, conventions).
> Scope: MVP + MLP (the demo threshold). V1/V2 are noted only where they constrain a choice made today.
> Last updated: July 2026 — architecture session.

---

## 0. Notes for Fable

- **This is a sketch.** Module boundaries, responsibilities and interfaces are the point. Signatures are indicative, not binding — refine them, then implement.
- **Follow `SCRANTON_CONTEXT.md` §8**: English code + docstrings, pedagogical comments (why, not what), explicit over clever, `/api/v1/...`, conventional commits. The codebase is a portfolio and a learning resource.
- **Honor the seams** (`PRODUCT_ROADMAP.md` §2): never hardcode a provider, a data source, or a character name/avatar. Each lives behind an interface or a config map.
- **Do not modify the validated data model** (`SCRANTON_CONTEXT.md` §5) without a dedicated session. This sketch only maps it to an ORM.
- **Design around the axes of variability (see §13).** The goal is not to build the backlog now, but to never foreclose it: swappable LLMs, storage on local / NAS / cloud, voice or text input, and ingestion from varied sources (WhatsApp, Apple Notes, email, ...). Every choice today must keep those doors open.
- **Never write code without an explicit go from the owner.**

---

## 1. High-level shape

Local-first **FastAPI monolith**, single process, runs on a Mac Mini for the POC.

- **SQLite** = structured/relational truth (the 8 tables). Facts, segments, tags, moods.
- **ChromaDB** (local, persistent) = one vector per segment, for semantic retrieval.
- **Swappable seams**: `LLMProvider`, `IngestionSource`, `VectorStore`, and a `characters` config map (which doubles as the **agent registry**).
- **Frontend**: HTML/CSS/JS (no framework), talks only to `/api/v1`.

Each service implements one **agent** with a narrow mandate (Dwight structures, Pam remembers, Toby aggregates), all sharing the same memory. The orchestrator is the manager, by design: agents propose, the human validates (see SCRANTON_CONTEXT §1, "Agent architecture — human-orchestrated").

```
[ Frontend HTML/CSS/JS ]
          │  HTTP /api/v1
          ▼
[ FastAPI routers ]  dwight · pam · mood · toby · health
          │
          ▼
[ Services ]  DwightService · PamService · MoodService · TobyService
     │                 │                │
     ▼                 ▼                ▼
[ Adapters ]     [ Repositories ]   [ VectorStore ]
 LLMProvider      SQLAlchemy ORM      ChromaStore
 IngestionSource  (SQLite)
 (Mistral/Gemini,
  GDrive/Local)
```

The manager remains the sole decision-maker; the AI structures and surfaces, never decides (SCRANTON_CONTEXT §1).

---

## 2. Backend module layout (proposed)

```
backend/
  app/
    main.py               # FastAPI app factory, mounts routers, lifespan (db init)
    config.py             # Settings from .env (LLM_PROVIDER, keys). python-dotenv.
    api/v1/
      health.py           # GET /health
      dwight.py           # capture + validation endpoints
      pam.py              # query endpoints
      mood.py             # Pretzel Day check-ins
      toby.py             # Meet Toby v0 overview
    services/
      dwight_service.py   # capture -> segment -> classify -> route -> embed
      pam_service.py      # query -> retrieve -> grounded answer
      mood_service.py     # record + trend
      toby_service.py     # aggregate mood + weak signals (no scoring of people)
    adapters/
      llm/
        base.py           # LLMProvider (ABC)
        mistral.py        # MistralProvider  (from mistralai.client import Mistral)
        gemini.py         # GeminiProvider   (fallback)
        factory.py        # build from config.LLM_PROVIDER
      ingestion/
        base.py           # IngestionSource (ABC)
        local.py          # LocalSource (files / manual entry) -- MVP
        gdrive.py         # GDriveSource (OAuth + Drive API) -- MLP
        factory.py
      vectorstore/
        base.py           # VectorStore (ABC)
        chroma.py         # ChromaStore
    domain/
      models.py           # SQLAlchemy ORM = the 8 tables (SCRANTON_CONTEXT §5)
      schemas.py          # Pydantic request/response models
      characters.py       # character config map (names + avatars), IP-safe seam
    db/
      session.py          # SQLite engine + session factory
      init_db.py          # create tables; seed the fictitious Dunder Mifflin dataset
  tests/
    conftest.py           # fixtures, FakeLLMProvider
    ...
```

---

## 3. The swappable seams (interfaces)

Indicative signatures — Fable refines.

**`LLMProvider` (ABC)** — every model call goes through this.
```python
class LLMProvider(ABC):
    def complete(self, messages: list[dict], *, model: str | None = None) -> str: ...
    def embed(self, texts: list[str]) -> list[list[float]]: ...
```
- `MistralProvider`: `from mistralai.client import Mistral` (mistralai 2.x — namespace package, not the 1.x `from mistralai import Mistral`). Default model `mistral-small-latest`.
- `GeminiProvider`: fallback if routing/extraction quality is short.
- `factory.build_llm(settings)` selects by `settings.LLM_PROVIDER`.

**`IngestionSource` (ABC)** — where raw material comes from.
```python
class IngestionSource(ABC):
    def fetch(self) -> Iterable[RawDoc]: ...   # RawDoc: {content, source_type, origin_ref}
```
- `LocalSource` (MVP): manual Tell Dwight input and/or local files.
- `GDriveSource` (MLP): OAuth consent, read a chosen folder, pull Google Docs/PDF/txt, normalize to `RawDoc`.
- Every `RawDoc` enters the **same** Tell Dwight pipeline (see §4). Treat it as a **connector registry**: `GDriveSource` is the first of many — WhatsApp export, Apple Notes, email, Dropbox/OneDrive, SME systems. Source-specific details never leak past the adapter; the pipeline only ever sees `RawDoc`.

**`Transcriber` (ABC)** — input-modality seam, so voice is never a special case.
```python
class Transcriber(ABC):
    def transcribe(self, audio: bytes) -> str: ...
```
- Impls (V2): whisper.cpp local, Web Speech, or Mistral STT. Voice input (Tell Dwight "in the truck", Whisper Jim) becomes `Transcriber` → text → the same §4 pipeline. **Text stays the single internal representation**, so nothing downstream cares whether an input was typed or spoken.

**`VectorStore` (ABC)** — semantic index.
```python
class VectorStore(ABC):
    def upsert(self, segments: list[SegmentVector]) -> None: ...
    def query(self, text: str, *, filters: dict, k: int = 8) -> list[Hit]: ...
```
- `ChromaStore`: local persistent client, one collection `segments`, metadata per SCRANTON_CONTEXT §5 (segment_id, data_type, sensitivity_level, flattened entity/view tags).

**`characters` config map** — IP-safe rebrand seam.
```python
CHARACTERS = {"dwight": {"display_name": "Tell Dwight", "avatar": "dwight.png"}, ...}
```
Routes and UI reference keys only. Rebrand = edit this map + swap assets.

---

## 4. Data flow — Tell Dwight (capture engine, MVP)

1. `POST /api/v1/dwight/entries` `{raw_content, source_type, submitted_by_id?}`
2. Persist an `entries` row — **immutable**, `processing_status = pending`.
3. `DwightService` calls `LLMProvider.complete(...)` to **segment** the raw text, **reformulate** each chunk, **classify** it (`data_type` cold/warm, `sensitivity_level` 1–5), and **propose tags** (`entity_type`/`view_type`, `entity_id?`, `confidence`). Dwight asks a follow-up question when input is too vague.
4. Persist `entry_segments` (`validation_status = proposed`) + `segment_tags` (`proposed_by = dwight`, `validated = false`).
5. `LLMProvider.embed(...)` each segment → `VectorStore.upsert(...)` with metadata.
6. Return proposed segments + tags for validation.
7. `POST /api/v1/dwight/segments/{id}/validate` → set `validated` / `validation_status`. POC (single manager): manager validates all. V2: emitter validates own (`submitted_by_id` already anticipates it).

Raw entries are never modified; only segments are processed and routed (SCRANTON_CONTEXT §5).

---

## 5. Data flow — Ask Pam (memory engine, MVP)

1. `POST /api/v1/pam/query` `{question}`.
2. Optional clarify step: Pam asks a narrowing question if the query is ambiguous.
3. `LLMProvider.embed(question)` → `VectorStore.query(text, filters, k)` → top-k segments (semantic + metadata filters, e.g. by project/member/view, honoring `sensitivity_level`).
4. `LLMProvider.complete(...)`: answer **grounded only in retrieved segments**, with sources.
5. Return `{answer, sources[]}`. Text now; voice output is V2.

---

## 6. Data flow — Pretzel Day + Meet Toby v0 (feel-better engine, MLP)

- `POST /api/v1/mood/checkins` `{team_member_id, mood_level, note?}` → `mood_checkins`. `mood_level` ∈ flow/ctrl/pretzel_day/press/stuck/danger. Attributed, not anonymous.
- `GET /api/v1/toby/overview` → aggregate: mood trend per member + team, plus weak signals surfaced from warm segments. **No scoring, ranking, or performance metric on any person** (north star + anti-surveillance spine). Manager-only visibility.

---

## 7. Ingestion — Google Drive first connector (MLP)

- `GDriveSource.fetch()`: OAuth user consent → list a chosen Drive folder → pull docs → normalize to `RawDoc`.
- Each `RawDoc` runs the §4 Tell Dwight pipeline (entries → segments → tags → vectors). No new pipeline.
- Privacy note: Drive is a tester-onboarding convenience; sovereign/local ingestion is the V2 target. Keep the seam clean so a local/SME source drops in later.

---

## 8. Config, secrets, persistence

- **Config**: `app/config.py` loads `.env` via python-dotenv → `Settings` (`LLM_PROVIDER`, `MISTRAL_API_KEY`, `GEMINI_API_KEY`, later `GOOGLE_*` OAuth). `.env` is git-ignored; `.env.example` is the versioned template.
- **SQLite**: SQLAlchemy models = SCRANTON_CONTEXT §5 (8 tables). One local file under `data/`. Alembic optional later; `init_db.py` is enough for the POC.
- **ChromaDB**: persistent client under `data/`, collection `segments`.
- **Data location is config, not code**: the SQLite URL and the ChromaDB directory come from settings, so the same build runs on local disk, a **Synology NAS** mount, or a cloud volume. The Repository layer hides the store, so SQLite can later become Postgres (multi-user / cloud) without touching services.

---

## 9. API surface (v1) — first cut

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/health` | liveness |
| POST | `/api/v1/dwight/entries` | submit raw input, get proposed segments |
| POST | `/api/v1/dwight/segments/{id}/validate` | validate/adjust routing |
| POST | `/api/v1/pam/query` | plain-language question over memory |
| POST | `/api/v1/mood/checkins` | Pretzel Day check-in |
| GET | `/api/v1/toby/overview` | mood trends + weak signals |
| POST | `/api/v1/ingest/gdrive` | trigger a Google Drive pull (MLP) |

---

## 10. Testing & QA

- **pytest**. Each service unit-tested against a **`FakeLLMProvider`** (deterministic, no network) so tests are fast and free. The real Mistral call becomes an **integration smoke test** behind a marker (the connectivity ping already proved the wiring).
- **Anti-regression** (SCRANTON_CONTEXT §11): seed dataset + a set of golden Ask Pam queries with expected sources; run on every feature.
- QA protocols defined from the first deliverable, not retrofitted.

---

## 11. Build order (mirrors PRODUCT_ROADMAP §10 milestones)

| Milestone | Build | Push |
|---|---|---|
| **M0** | skeleton + config + db init + the four interfaces (with `Fake`/`Local`/`Chroma` stubs) + `/health` + first tests | ✅ |
| **M1** | Tell Dwight pipeline on `MistralProvider` | ✅ |
| **M2** | Ask Pam on `ChromaStore` — **MVP done** | ✅ |
| **M3** | Pretzel Day + Meet Toby v0 + That's What She Said + UI shell + `GDriveSource` + seed — **MLP done, demo-ready** | ✅ |

---

## 12. Left open for Fable to decide

- Exact model per task (small vs medium) and prompt design for segmentation/routing.
- Chunking/embedding strategy (segment = chunk, or sub-chunk long segments?).
- Sync vs async pipeline; background task/queue for ingestion (Drive pulls can be slow — the roadmap's async "in the truck" mode is V2 but the seam can anticipate it).
- OAuth library and token storage for Google Drive.
- ORM details: Alembic now or later; indexing strategy on `segment_tags`.

---

## 13. Extensibility axes — do not foreclose these

The backlog is **not built now**, but today's structure must keep every one of these doors open. Each axis of future variability gets a **seam** so change means adding an adapter, never rewriting the core. The "anti-pattern" column is what would quietly close the door.

| Axis of variability | Seam that keeps it open | Future implementations (backlog) | Anti-pattern to avoid |
|---|---|---|---|
| Reasoning & embeddings | `LLMProvider` | Sovereign/local models (Albert, Ollama, llama.cpp), other cloud LLMs | Calling a vendor SDK directly from a service |
| Input modality (text ↔ voice) | `Transcriber` upstream of Dwight | whisper.cpp, Web Speech, Mistral STT; Tell Dwight voice, Whisper Jim | Assuming an entry is always typed text |
| Input **source** | `IngestionSource` connector registry → `RawDoc` | WhatsApp export, Apple Notes, email, Dropbox/OneDrive, SME systems | Source-specific fields leaking past the adapter |
| Data **location** | Config-driven paths/URLs + Repository layer | Local disk, Synology NAS, cloud volume; SQLite → Postgres | Hardcoded absolute paths; SQLite-only SQL in services |
| Single- ↔ multi-user | Identity/actor context threaded through services (+ `submitted_by_id`) | Auth, per-emitter validation | Hardcoding "the manager"; dropping actor context |
| Vector store | `VectorStore` | Remote/managed vector DB | Chroma-specific calls in services |
| Output & notifications | `OutputChannel` / `Notifier` + `Exporter` | Maire birthday reminders, voice output, Send Angela (PDF/Grist/Docs) | Formatting or rendering inside services |
| Portability / handover | A defined **JSON serialization contract** (SQLite subset + Chroma subset, filtered by ownership + `sensitivity_level`, soft-delete + audit) | Transfer to Philly cases 1 & 2, instance transfer, ecosystem interop | No export contract (forces rework); hard deletes (lose audit trail) |
| Scheduling / async | A light scheduler / task-queue seam | Birthday reminders, async "in the truck" batch, periodic ingestion | Assuming everything is synchronous request/response |

**Cross-cutting principles that make the above cheap:**
- **Normalize at the edge.** Every external input becomes a `RawDoc`; every model call goes through `LLMProvider`; services never see a vendor or a source format.
- **Config over code for anything physical** — data location, provider, model, credentials, source folder.
- **Thread identity from day one.** Pass an actor/identity context through services even while single-user, so multi-user is additive.
- **Define portable formats early.** Sketch the handover/export JSON contract now even though the feature ships in V1 — it is the cheapest insurance against a painful rewrite, and it also constrains the ChromaDB metadata design.
- **Keep domain logic pure.** No file I/O, no HTTP, no formatting inside services — those belong in adapters. A service should be testable with fakes and no network.

None of this adds build cost to the MVP/MLP: it is the *shape* of the seams, not extra features. Build the simplest impl behind each seam (Local, Mistral, Chroma, single-user), and the backlog plugs in later.

---

*End of sketch. This is a draft to be refined before any code is written — and no code without the owner's go.*
