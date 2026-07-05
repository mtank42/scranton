# SCRANTON — PRODUCT ROADMAP
> Single source of truth for **what** gets built and **in what order**.
> Companion to `SCRANTON_CONTEXT.md` (architecture, data model, conventions) and `BACKLOG.md` (feature briefs).
> Audience: a capable LLM agent (Fable 5 or equivalent) planning and building the POC, plus the human owner.
> Last updated: July 2026 — roadmap session.

---

## 0. How to use this document

This file defines the product tiers (MVP / MLP / V1 / V2), the prioritized backlog, prerequisites, and dependencies.

Read order for an agent picking up the project:
1. This file — the **plan**.
2. `SCRANTON_CONTEXT.md` — the **architecture, data model, stack, conventions**.
3. `BACKLOG.md` — the **detailed briefs** for post-MLP features.

Rules of engagement (from the owner, non-negotiable):
- **Never write code without an explicit go.** Surface options and consequences first.
- Ask only blocking questions, 3–6 max per exchange.
- Do not modify the validated data model without a dedicated session.

---

## 1. North star — the decision filter

> **Scranton helps a team feel better. It is not a performance tool.**
> Performance is a *consequence* of well-being, never a metric Scranton measures.

Every scope decision is filtered through this. If a feature measures, ranks, or surveils people, it is off-thesis — no matter how useful it looks. Scranton captures the human layer so the manager stops dropping it, and surfaces how the team feels so the manager can act. That is the whole product.

This is what separates Scranton from Lattice / 15Five / Viva (performance and HR reporting) and from Notion / Obsidian (a notebook with no mood layer and no team view).

---

## 2. Cross-cutting principles (apply to every tier)

These are not features. They are constraints that shape every feature.

1. **Anti-surveillance is the spine, not a layer.** The manager protects the team's data. The ownership split is real and visible: professional data = manager; personal data (`personal_profile`, `birthday`) = the team member. No feature ever scores or ranks a person. `sensitivity_level` and cold/warm are honored everywhere.
2. **Provider- and source-agnostic by design.** Every LLM/embedding call goes through one `LLMProvider` interface (Mistral, Gemini Flash, or other — swappable by config). Every data source goes through one `IngestionSource` interface: MVP uses any source (the owner's local files or his own Drive — these are his own tests, it does not matter); MLP uses the **user's own** data via a **Google Drive** connector first, with the interface built to add others (Dropbox, OneDrive, local folder, SME systems) without rework. Vectors live in local ChromaDB behind a `VectorStore` interface. Testability wins over provider purity for the POC. Sovereign/local (Mistral, Albert, on-prem) is the **V2 product target**, not a POC constraint. "Bring-your-own-LLM" and "bring-your-own-data-source" are themselves product arguments.
3. **Character layer is swappable config.** Display names (Tell Dwight, Ask Pam, ...) and avatars never appear hardcoded in routes or UI. They live in one `character → {display_name, avatar_asset}` map. This makes the eventual IP-driven rebrand a config change, not a refactor (see §8 Risks).
4. **The codebase is a portfolio and a learning resource.** English code + docstrings, pedagogical comments (why, not what), explicit over clever. Repo stays clean and demo-ready at all times.

---

## 3. Product tiers

### Definitions

| Tier | Meaning | Shown to anyone? |
|---|---|---|
| **MVP** | The indivisible engine that proves the memory loop works. | **No.** Internal build milestone only. |
| **MLP** | Minimum **Lovable** Product. MVP + the feel-better loop + one cheap delight, in a modern UI. **This is the demo threshold.** | **Yes — this is the first thing shown to testers/recruiters. Nothing is shown before it.** |
| **V1** | Post-demo depth: rituals, human profile, handover, summaries. | Yes, to engaged testers. |
| **V2** | Sovereign hardening, voice, multi-user, ecosystem, rebrand. | Product phase, if it goes serious. |

### MVP — the memory engine

**Goal:** prove that nothing human is lost. Capture free text, structure it silently, retrieve it in plain language.

| Feature | Why it is MVP | Effort |
|---|---|---|
| **Tell Dwight** | Universal capture → segmentation → routing via the LLM. The foundation every other feature reuses (segments + tags). | L |
| **Ask Pam** | RAG over the segments. Capture without retrieval proves nothing; the two only make sense together. Highest recruiter signal (LLM pipeline + RAG). | L |

**Definition of done:** a manager types a messy note, Dwight segments/routes/validates it into the SQLite + ChromaDB layer, and Ask Pam answers a plain-language question over the accumulated history. Provider and storage are already behind interfaces.

### MLP — the demo threshold (feel-better loop + delight)

**Goal:** cross from *useful* to *loved*. Add the mood engine (the north star made concrete) and the finish that makes it a joy to use.

| Feature | Why it is MLP | Effort |
|---|---|---|
| **Pretzel Day** | Must-have. The 30-second mood check-in — the most on-thesis feature. The owner will not show the product without it. | S |
| **Meet Toby v0** | The payoff surface: manager sees mood trends + weak signals and can act. Minimal version (trend view), not the full equity dashboard. | M |
| **That's What She Said** | Cheap, high-delight micro-reward on completion. The "L" garnish while Maire de Scranton waits. | S |
| **Modern UI shell (2026)** | Simple, beautiful, visible micro-interactions. Design system colors + IBM Plex intact; avatars kept for now (see Risks). No heavy framework. | M |
| **Google Drive ingestion** (1st source connector) | For a real tester to *use* Scranton, their own data must get in. Drive first, behind a pluggable `IngestionSource`. Adds OAuth + Drive API — the heaviest MLP item. | M–L |

**Definition of done:** a manager runs a daily Pretzel Day check-in, sees the team's mood trend and weak signals in Meet Toby v0, captures/queries via Dwight+Pam, gets a That's What She Said reward — all in a polished modern UI. Runs on the seeded Dunder Mifflin dataset for a recruiter demo, or on a tester's own Google Drive content. This is the 10-minute demo.

### V1 — post-demo depth

| Feature | Depends on | Effort | Priority |
|---|---|---|---|
| **Profil humain** ("what they love") | Dwight extraction, data-ownership split | M | Must (enables Maire) |
| **Maire de Scranton** (birthday ritual) | Profil humain, `birthday`, Pam reminders, That's What She Said | M | Should (rare event in small teams — deprioritized vs Pretzel Day) |
| **Transfer to Philly — case 1** (single handover + validated PDF) | cold/warm segments, `sensitivity_level`, emitter validation, export | L | Should (GDPR differentiator) |
| **Smart Summaries** (6 living templates) | Dwight + Pam, `view_type`s | L | Should |
| **Send Angela** (one-click export) | Smart Summaries / segments | M | Could |

### V2 — product phase (if it goes serious)

| Feature | Notes |
|---|---|
| **Tell Dwight — voice capture** (async batch, "in the truck") | Needs sovereign transcription (whisper.cpp local / Web Speech / Mistral STT) + PWA. `source_type = voice_note`, no schema change. |
| **Transfer to Philly — case 2** (batch + instance transfer + interop) | Needs an export/import format defined early to avoid rework. |
| **Whisper Jim** (ephemeral chat, Invite Dwight vote) | Not in POC. |
| **Sovereign hardening** | E2EE (SQLCipher), EU sync (Hetzner/OVH + CRDTs), NER sanitiser before any cloud call, local-only provider mode. This is where the privacy pitch becomes literally true. |
| **Multi-user + auth** | `submitted_by_id` already anticipates it; emitters validate their own submissions. |
| **Ecosystem** | LaSuite (Grist Core for Send Angela, Docs for summaries), Albert API (sovereign LLM), data.gouv MCP pattern. |
| **Clean-room rebrand** | Replace The Office names + avatars via the character config map (see Risks). |
| **Billing connector** | Send Angela → invoicing tool, TBD. |

---

## 4. Prioritized backlog (one glance)

MoSCoW within the POC horizon (MVP + MLP). Everything below MLP is **Won't (now)** for the POC build.

| # | Item | Tier | Priority (POC) | Effort |
|---|---|---|---|---|
| 1 | Tell Dwight | MVP | Must | L |
| 2 | Ask Pam | MVP | Must | L |
| 3 | Pretzel Day | MLP | Must | S |
| 4 | Meet Toby v0 | MLP | Must | M |
| 5 | Modern UI shell | MLP | Must | M |
| 6 | That's What She Said | MLP | Should | S |
| 7 | Google Drive ingestion (source adapter) | MLP | Must (for real testers) | M–L |
| 8 | Profil humain | V1 | Won't (now) | M |
| 9 | Maire de Scranton | V1 | Won't (now) | M |
| 10 | Transfer to Philly — case 1 | V1 | Won't (now) | L |
| 11 | Smart Summaries | V1 | Won't (now) | L |
| 12 | Send Angela | V1 | Won't (now) | M |
| 13+ | Voice capture, Transfer case 2, Whisper Jim, sovereign hardening, ecosystem, rebrand, billing | V2 | Won't (now) | — |

---

## 5. Prerequisites

Before **any** MVP code:

| Prerequisite | Status (July 2026) | Notes |
|---|---|---|
| Python venv | ✅ created | `.venv` on **Python 3.12.10** (`/usr/local/bin/python3.12`). 3.14 dropped: too new, de-risks ChromaDB. `mistralai` + `python-dotenv` installed. |
| `requirements.txt` / deps | ❌ none | fastapi, uvicorn, mistralai, chromadb, python-dotenv, etc. Freeze once M0 deps settle. |
| LLM provider key | ✅ validated | Mistral key in local `.env` (git-ignored). Connectivity ping to `mistral-small-latest` succeeded. Gemini fallback ready if quality is short. |
| `.env.example` | ✅ | Versioned template (`LLM_PROVIDER`, `MISTRAL_API_KEY`, `GEMINI_API_KEY`); real `.env` never committed. |
| FastAPI skeleton | ❌ | `backend/` structure, `/api/v1/...`, auto-docs. |
| Provider + storage + character interfaces | ❌ | Stub `LLMProvider`, storage/ingestion, and `character` config **before** feature code, so nothing hardcodes a provider or a name. |
| Demo dataset | ❌ | Fictitious Dunder Mifflin team + ~3 months history, for MLP demo. |

---

## 6. Dependency graph

Build order is constrained by these edges (A → B means "A must exist before B").

```
Data model (done) ────────────────────────────────────┐
                                                       │
LLMProvider interface ──► Tell Dwight ──► Ask Pam       │
storage/ingestion iface ─►    │            ▲            │
                              │            │            │
                              └── segments ─┘            │
                                                        │
team_members + mood_checkins ─► Pretzel Day ─► Meet Toby v0
                                                        │
task/commitment completion ─► That's What She Said      │
                                                        │
UI shell (cross-cutting) ─► all user-facing features ───┘

--- V1+ (post-demo) ---
Tell Dwight extraction ─► Profil humain ─► Maire de Scranton (+ birthday, Pam reminders, That's What She Said)
cold/warm + sensitivity + validation ─► Transfer to Philly case 1 ─► case 2 (V2)
Dwight + Pam + view_types ─► Smart Summaries ─► Send Angela
```

Critical path to the demo: **interfaces → Tell Dwight → Ask Pam → Pretzel Day → Meet Toby v0 → UI shell → Google Drive source**. Pretzel Day is independent of the Dwight/Pam engine and can be built in parallel once the UI shell exists. The Google Drive `IngestionSource` feeds Tell Dwight (its output is the same `entries` pipeline), so it lands after Tell Dwight is stable.

---

## 7. Architecture decisions carried into build

Settled; do not re-litigate without a session.

- **Data model**: validated (8 SQLite tables, 10 view_types, 1 ChromaDB collection). See `SCRANTON_CONTEXT.md` §5. cold/warm and `sensitivity_level` are native at the segment level.
- **LLM/embeddings**: behind `LLMProvider`. Start with the best-quality option for the demo; `mistral-small` was the original default but Gemini Flash (or other) is fair game if routing/extraction quality demands it. Note: mistralai 2.x is a namespace package - the client import is `from mistralai.client import Mistral` (not the 1.x `from mistralai import Mistral`).
- **RAG/source**: vectors in ChromaDB local (behind `VectorStore`); data source behind `IngestionSource` (MVP: local / owner Drive; MLP: user's Google Drive first, extensible). Export format for ChromaDB matters for Transfer to Philly case 2 — design it before that feature, not after.
- **Character layer**: names + avatars in one swappable config map.
- **Auth**: none for POC (localhost, single manager). `submitted_by_id` nullable anticipates V2 multi-user.
- **Stack**: FastAPI + SQLite + ChromaDB + HTML/CSS/JS (no framework). Python 3.11+ (system is 3.14 — verify lib compat).

---

## 8. Risks & mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| **IP / trademark** — the entire brand (Scranton, Tell Dwight, Ask Pam, That's What She Said, avatars) is The Office IP. Names are a bigger exposure than the avatars. | Blocks commercialization. | Keep for the portfolio demo (non-commercial, low risk). Character config map makes rebrand a config change. V2 backlog item: **clean-room rebrand** (names + avatars together). |
| **Provider quality** — Mistral routing/extraction may be "meh". | Weak core demo. | Provider abstraction lets us benchmark Mistral small/medium vs Gemini Flash and pick per task. |
| **Privacy vs testability tension** — using Gemini / Google Drive for easy testing contradicts the anti-surveillance pitch. | Credibility gap if unspoken. | Be explicit in the demo: "architecture is provider-agnostic; the sovereign, local deployment is the product (V2)." The abstraction is the proof the pitch is real. |
| **Scope creep** — announced features pulling into the POC. | Missed demo. | Only the MLP is built during the POC. Everything else is Won't (now). |
| **Python 3.14 lib compat** (ChromaDB). | Setup friction. | Verify on `pip install`; fall back to a pinned 3.11 via pyenv only if a core lib breaks. |

---

## 9. Open questions to resolve before the relevant tier

- **[MVP] Provider default — RESOLVED (2026-07):** start on `mistral-small-latest` (connectivity validated); escalate small → medium → Gemini Flash empirically once Tell Dwight makes routing quality measurable. No abstract benchmark now.
- **[MLP] Google Drive role — RESOLVED (2026-07):** data source is pluggable (`IngestionSource`). MVP: any source (owner's local/Drive, his own tests). MLP: the *user's own* data via a Google Drive connector first, interface built to add others later. Ingestion output reuses the `entries` pipeline.
- **[V1] `personal_profile`: free text or structured table?** Free text is natural to enter; structured enables Pam correlations ("two people love jazz"). See `BACKLOG.md`.
- **[V1] Dwight auto-extraction of personal info: systematic proposal or on-demand?** Consent-sensitive.
- **[V1] Transfer to Philly: validation traceability** — `handover_validations` table shape (statuses + timestamps; signatures or boolean?).

---

## 10. Suggested milestones = commit/push checkpoints

Work happens locally (to test freely). Recommend a commit + push to GitHub at each milestone below — the repo stays clean and portfolio-ready throughout.

| Milestone | Contents | Push checkpoint |
|---|---|---|
| **M0 — Skeleton** | FastAPI structure, `.env.example`, stubbed `LLMProvider` / storage / character interfaces, deps, first tests. | ✅ commit + push |
| **M1 — Dwight** | Tell Dwight capture → segment → route pipeline, persisted to SQLite. | ✅ commit + push |
| **M2 — Pam (MVP done)** | Ask Pam RAG over ChromaDB, plain-language answers. | ✅ commit + push |
| **M3 — Feel-better + UI (MLP done = demo-ready)** | Pretzel Day, Meet Toby v0, That's What She Said, modern UI shell, demo dataset. | ✅ commit + push |
| **V1 milestones** | One push per feature (Profil humain, Maire, Transfer case 1, Smart Summaries, Send Angela). | ✅ per feature |

---

*End of roadmap. Update this file whenever a tier boundary or priority changes; it is the plan of record.*
