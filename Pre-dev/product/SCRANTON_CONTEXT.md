# SCRANTON — PROJECT CONTEXT
> Feed this file to Claude Code at the start of every session.
> Location: `Pre-dev/product/SCRANTON_CONTEXT.md` (moved from repo root, July 2026 — repo cleanup).
> Product tiering (MVP / MLP / V1 / V2), prioritized backlog and dependencies live in `Pre-dev/product/PRODUCT_ROADMAP.md` — the single source of truth for what gets built and in what order.
> Last updated: July 2026 — agentic framing named (human-orchestrated agents, see §1); previously: product roadmap session (MVP/MLP defined, provider abstraction decided)

---

## 1. What is Scranton

A **managerial operating system** for proximity managers in SMEs without dedicated HR or IT.
Local-first, E2EE-ready, Mistral AI, anti-Workday, anti-surveillance.

Inspired by the worst manager on American TV. Built for the best.
**One smart notepad. Zero bureaucracy. 100 % team.**

### The problem it solves
1. **Meeting overload** — managers spend more time documenting than managing
2. **The human blind spot** — weak signals (burnout, disengagement) are never captured in time
3. **Tools built for HR, not managers** — Workday, HRIS, spreadsheets serve compliance, not the human managing a team every day

### Core philosophy
AI is never visible as a decision-maker. It structures, summarises, detects — silently.
The manager remains the sole source of every human decision.

### Agent architecture — human-orchestrated (naming settled July 2026)
The character features (Tell Dwight, Ask Pam, Meet Toby, Send Angela, ...) are **specialized agents**: each has a narrow mandate, and they share one collective memory (SQLite + ChromaDB). Agents interact — Smart Summaries are Dwight + Pam together, Maire de Scranton is Pam triggering That's What She Said. The `characters` config map is, in effect, the agent registry.

**The orchestrator is the manager — deliberately.** Agents propose (segments, routings, answers, reminders); the manager validates. This enters the agentic-orchestration conversation through the anti-surveillance door: *human-orchestrated agents*, never autonomous deciders. It is the north star made architectural.

**Calibration (do not overclaim):** in the POC, each agent is a deterministic LLM pipeline — no tool loops, no planning, no autonomy. Agency grows by tier: clarification dialogue (MVP), proactive reminders (V1: Pam, Maire de Scranton), async batch work (V2: voice capture "in the truck"). Pitch and README must never claim multi-agent autonomy that the code does not have.

---

## 2. Current status

- **Phase**: Pre-code. Architecture clarification done. Data model validated (May 2026) — see Section 5.
- **Goal**: Working POC in 4 months, demo-ready for portfolio and job search.
- **Owner**: Mathieu Tank — 25+ years digital Product/Ops/Editorial, currently in formation at École 42 (Python, Data, AI). This project IS the portfolio.
- **Stack decisions**: see Section 4.
- **Design assets**: slides deck v6 (scranton_slides_v6.html), 2-pager (scranton_2pager.html), roadmap (scranton_roadmap_demo.html). These are the visual reference and the storyboard. Do not redesign — extend.

### Architecture decisions settled (May 2026 session)
- **Auth**: no auth for dev (localhost, single manager). A demo-ready deployment is required for portfolio — see Section 4 (Hosting).
- **LLM provider (revised July 2026)**: provider-agnostic. All model calls go through one `LLMProvider` interface — swappable by config (Mistral, Gemini Flash, others). Start with whatever gives the best routing/extraction quality for the demo; testability wins over provider purity for the POC. Sovereign/local models (Mistral, Albert) become the *product* target in V2, not a POC constraint. "Bring-your-own-LLM" is a product argument, not just a dev convenience.
- **Repo structure**: `backend/` / `frontend/` / `data/` / `tests/` / `docs/`
- **Build tiering (revised July 2026 — see PRODUCT_ROADMAP.md)**: MVP = Tell Dwight + Ask Pam (memory engine, internal milestone, not shown). MLP = MVP + Pretzel Day + Meet Toby v0 + That's What She Said (the demo threshold — nothing is shown to anyone before this). Nothing outside the MLP is built during the POC.
- **Data model**: validated May 2026 — see Section 5. Do not modify without explicit session.
- **Cold/warm data distinction**: native in the schema at segment level — see Section 5.

---

## 3. Features — nomenclature (The Office universe)

All feature names are final. Do not rename.

| Feature name | Category | Description |
|---|---|---|
| **Tell Dwight** | Core / Input | Free-text universal input. Routes notes to correct destinations simultaneously. Asks follow-up questions if vague. Corrects tone and spelling. |
| **Ask Pam** | Memory / RAG | Collective memory, plain-language queries. Pam clarifies before answering. Drafts on demand. Text or voice output. Nothing ever lost. |
| **Whisper Jim** | Ephemeral chat | 1:1 and group chat, ephemeral by default. No AI, no indexing. "Pam needs to know this?" — unanimous vote triggers Invite Dwight. |
| **Pretzel Day** | Daily mood check-in | 30-second check-in. Flow→Danger palette (6 levels). Manager sees team trends. Remote, hybrid, on-site. |
| **Michael's Desk** | People Management | AI-assisted 1:1 management. Auto-extracted actions and commitments. Archived and searchable. Natively transition-proof via Transfer to Philly. |
| **Transfer to Philly** | Transitions / Handover | Structured handover when a team member moves or a manager is replaced. Cold data (facts) + warm data (manager observations), employee-validated, GDPR-compliant. Angela sends to next manager's Scranton. See BACKLOG.md for full spec. |
| **Meet Toby** | Dashboard / Equity | Aggregated team health: weak signals, mood trends, equity flags (pay, tasks, promotions). Manager-only visibility. |
| **Send Angela** | Export / Reporting | One-click export by project, member, or client. No retyping. Angela delivers, no questions asked. |
| **That's What She Said** | Reward | Visual reward + random Michael Scott quote on task completion. Customisable per user. |

### Smart Summaries (powered by Dwight + Pam together)
6 living templates, auto-fed by Tell Dwight, queryable via Ask Pam:
1. Team Member File
2. Project File
3. Client File
4. Team Radar (manager 360°)
5. Meeting Agenda + CR
6. Annual Review

### Reserved for fictitious users in mockups only
Ryan, Oscar, Kelly, Phyllis, Jan, Stanley, Kevin, Meredith, Creed, Darryl, Andy

---

## 4. Technical stack — decisions made

### Locked for POC
| Layer | Choice | Rationale |
|---|---|---|
| Language | Python 3.11+ | 42 curriculum, ecosystem for AI/data |
| API framework | FastAPI | Async, auto-docs, lightweight |
| LLM | Provider-agnostic via `LLMProvider` interface (Mistral, Gemini Flash, ...) | Testability first for POC; swap by config; sovereign target in V2 |
| Embeddings | Provider-agnostic via same abstraction | Follows the LLM provider choice |
| Vector store | ChromaDB (local) for POC; pluggable ingestion source (e.g. Google Drive) so testers do not need to wire their SME server | Simple to run + easy for testers to feed real data |
| Database | SQLite | Local-first, zero config, sufficient for POC |
| Frontend | HTML/CSS/JS (no framework) | Ship fast, no build tooling overhead |
| Fonts | IBM Plex Sans + IBM Plex Mono | Already in use across all design assets |

### Deferred to v2
- E2EE (SQLCipher or similar)
- EU server sync (Hetzner/OVH + CRDTs)
- NER sanitiser (anonymisation before any cloud call)
- Billing connector (Send Angela → invoicing tool TBD)
- Voice input/output (Whisper Jim full feature)
- Voice capture for Tell Dwight (async batch mode — see BACKLOG.md)

### Hosting — demo deployment
OVH shared hosting (800 MB) is insufficient — FastAPI does not run on shared hosting. Two options:
- **OVH VPS Starter** (~4€/month, 2 GB RAM, 20 GB SSD) — FastAPI + SQLite + ChromaDB, Mistral API calls. Recommended for a publicly accessible portfolio demo.
- **Mac Mini M4 as server** — always-on local server, accessible via domain. Valid for live demos.
Decision deferred to Month 4. POC runs on Mac Mini locally first.

### Hardware
- Dev + demo machine: Mac Mini M4
- Storage: Synology DS916+ NAS (backup, not primary)
- Remote access: iPad Air M2 via Jump Desktop

### Ecosystem reference
- **LaSuite numérique (DINUM)** — French sovereign open-source productivity suite. APIs available at `integration.lasuite.numerique.gouv.fr`. Relevant for future integrations and positioning. Same philosophy: sovereignty, open source, anti-surveillance.
- **Albert API** — French government sovereign LLM. Keep on radar as alternative/complement to Mistral if the project moves toward public sector or stronger EU sovereignty positioning.
- **data.gouv.fr MCP** — official French open data MCP server. Architecture pattern mirrors Ask Pam's RAG-on-live-data design.

---

## 5. Data model — validated May 2026 (+ handover session July 2026)

### SQLite tables (9)

| Table | Role |
|---|---|
| `team_members` | Team roster. `is_active` flag handles departures without deletion. |
| `entries` | Raw input received by Tell Dwight. Never modified after creation. |
| `entry_segments` | Dwight's output: segmented, reformulated, validated chunks. The real data layer. |
| `segment_tags` | Multi-dimensional routing keys. One row per tag per segment. |
| `clients` | Client entities. |
| `projects` | Project entities, optionally linked to a client. |
| `stakeholders` | Partners, subcontractors, investors, institutional contacts, secondary client contacts. |
| `mood_checkins` | Pretzel Day daily check-ins. Attributed (not anonymous). |
| `handover_validations` | Transfer to Philly consent trail (dedicated session, 2026-07-08). One record per handover: status, frozen selection, typed signatures, fiche hash. |

### Key fields

**`team_members`**
- `birthday` — date, used by Pam for the Maire de Scranton ritual and manager reminders
- `personal_profile` — free text or structured table (TBD in session): interests, passions, favorites. Owned and controlled by the team member. The manager cannot modify it. In POC (no auth): manager enters it on behalf. In V2: team member owns it directly.

**`entries`**
- `raw_content` — original text, never touched after creation
- `source_type` — note / meeting_cr / deliverable / quote / purchase_order / chat / transcript / voice_note
- `submitted_by_id` — FK team_members, nullable (null = manager submitted directly)
- `processing_status` — pending / processing / complete

**`entry_segments`**
- `content` — reformulated by Dwight
- `segment_order` — position within the source entry
- `data_type` — cold / warm (native from day one for Transfer to Philly)
- `sensitivity_level` — 1–5 (1: objective fact, 5: highly sensitive personal observation)
- `validation_status` — proposed / validated / rejected (emitter validates their own entry)

**`segment_tags`**
- `entity_type` — client / project / team_member / stakeholder / view
- `entity_id` — nullable FK to the relevant entity table
- `view_type` — see list below (only set when entity_type = view)
- `proposed_by` — dwight / manager
- `confidence` — float 0–1 (Dwight's confidence in this routing)
- `validated` — bool

**`stakeholders`**
- `relationship_type` — partner / subcontractor / investor / secondary_contact / institutional

**`mood_checkins`**
- `mood_level` — flow / ctrl / pretzel_day / press / stuck / danger
- `note` — nullable free text

**`handover_validations`** (session 2026-07-08 — full rationale in `docs/transfer_to_philly.md`)
- `status` — proposed / employee_reviewed / both_validated / sent, strictly forward
- `disclosed_warm_ids` — JSON text; the selection, mutable only while proposed
- `fiche_sha256` — hash of the markdown fiche, frozen at signature
- `manager_signature_name` + `manager_signed_at`, `member_signature_name` + `member_signed_at` — typed name + timestamp per party
- `created_at` / `reviewed_at` / `validated_at` / `sent_at` — one timestamp per transition

### View types (10)

| View type | What it feeds |
|---|---|
| `team_member_file` | Individual profile: skills, history, observations, signals |
| `project_file` | Everything on a project: decisions, deliverables, team, tech choices |
| `client_file` | Client relationship: history, preferences, commitments, feedback |
| `meeting_agenda` | Upcoming meeting preparation, auto-assembled by Pam |
| `meeting_cr` | Meeting record: decisions, actions, participants |
| `annual_review` | Year-long brief per team member, assembled by Pam |
| `idea_box` | Unrouted ideas, suggestions, future considerations |
| `team_radar` | Aggregated team health: mood trends, equity signals, load balance |
| `commitment` | Explicit commitments made to clients, team members, investors |
| `retrospective` | Project-close synthesis: what worked, what didn't, what to carry forward |

### ChromaDB

Single collection: `segments`. One vector per `entry_segment`.
Metadata: `segment_id`, `data_type`, `sensitivity_level`, entity tags and view tags (flattened lists).
Pam queries by semantic similarity + metadata filters.

### Design principles baked into the schema

- Raw entries are immutable. Only segments are processed and routed.
- cold/warm is at the segment level, not the entry level — Dwight can classify a paragraph as warm inside a mostly cold note.
- `sensitivity_level` is native for Transfer to Philly selective disclosure (V1).
- Validation is by the emitter. In POC (single manager, no auth): manager validates all. In V2: team members validate their own submissions.
- `submitted_by_id` nullable anticipates V2 multi-user without changing the schema.
- **Data ownership split**: professional data (notes, 1:1s, project work) belongs to the manager. Personal profile data (`personal_profile`, `birthday`) belongs to the team member. They disclose only what they choose. In V2, team members edit their own profile directly.

---

## 6. POC Roadmap — 4 months / 16 weeks

### Month 1 — Foundations
- **W1–W2**: Specs + architecture locked. Repo created. FastAPI skeleton running.
- **W2–W4**: Tell Dwight live. Mistral NER routes notes. First Smart Summary generated.

### Month 2 — Memory & mood
- **W5–W7**: Ask Pam live. ChromaDB vector store. Plain-language queries return structured answers.
- **W7–W8**: Pretzel Day live. Check-in UI, mood palette, manager trend view.

### Month 3 — UX cohesion
- **W9–W11**: Dashboard (Meet Toby v0) + 6 Smart Summary templates. Manager view + team member view.
- **W11–W12**: UX polish. Self-test with fictitious Dunder Mifflin dataset. That's What She Said reward.

### Month 4 — Demo-ready
- **W13–W15**: Clean deployment on Mac Mini. Pre-loaded demo dataset (fictitious team, 3 months history). 10-minute demo script.
- **W16**: GitHub repo clean + README. LinkedIn post. Live demo on request.

### If it becomes serious (post-POC)
User research → closed beta → legal/trademark → E2EE architecture → pricing → launch.

---

## 7. Design system — do not deviate

All UI must match the existing design assets exactly.

### Colours (CSS variables)
```css
--black:   #0a0a0a;
--yellow:  #F5C518;
--cyan:    #00D4FF;
--white:   #F0EDE8;
--grey:    #242424;
--midgrey: #aaa;
--ltgrey:  #ccc;
--red:     #E63946;
--green:   #00C853;
--purple:  #7B61FF;
--orange:  #FF6D00;
```

### Typography
- **IBM Plex Sans** (300 / 400 / 700 / 900) — body, headings
- **IBM Plex Mono** (400 / 700) — labels, tags, metadata, code

### Mood palette (Pretzel Day)
| State | Colour |
|---|---|
| Flow | `--green` #00C853 |
| Ctrl | `--cyan` #00D4FF |
| Pretzel Day | `--purple` #7B61FF |
| Press | `--yellow` #F5C518 |
| Stuck | `--orange` #FF6D00 |
| Danger | `--red` #E63946 |

### Character avatars (PNG, removebg)
Located in `assets/` directory:
- `michael-removebg-preview.png`
- `dwight-removebg-preview.png`
- `pam-removebg-preview.png`
- `jim-removebg-preview.png`
- `angela-removebg-preview.png`
- `toby-removebg-preview.png`

---

## 8. Coding conventions

- All code comments in **English** — exchanges with Mathieu are in French, everything in the codebase is in English
- Comments must be **pedagogical**: explain why, not just what. Mathieu is learning Python/AI at École 42 in parallel — the codebase is also a learning resource.
- All UI text in **English**
- No em dash (—) in code comments or strings — use colon or hyphen
- No emoji in UI unless explicitly specified (That's What She Said reward is an exception)
- Prefer explicit over clever: this codebase will be shown to recruiters
- Every function must have a docstring
- FastAPI routes: RESTful, versioned (`/api/v1/...`)
- Commit messages: conventional commits (`feat:`, `fix:`, `chore:`, etc.)

---

## 9. Competitive positioning (for context, not for UI)

| Competitor | Their weakness | Our answer |
|---|---|---|
| Lattice / 15Five / Leapsome | Built for HR reporting | Local-first, data belongs to manager not company |
| Notion + AI / Obsidian | No mood layer, no team view, no action extraction | A notebook is not an OS |
| Microsoft Viva | Surveillance dressed as wellbeing. Data flows to HR and Microsoft | The exact opposite: manager protects team data |

---

## 10. The pitch (for README and LinkedIn)

> A 25-year digital manager came back from École 42 at 56,
> learned Python and AI from scratch,
> and built his own management OS.
> Local-first. Mistral-powered. Anti-surveillance.
> Demo available on request.

---

## 11. Documentation and QA standards (every session)

- **README**: kept up to date at every significant change.
- **One .md per component**: each feature/module has its own doc in `docs/`.
- **QA protocols**: defined from the first deliverable, not retrofitted.
- **Anti-regression agents**: automated checks that a new feature doesn't break existing ones.
- **GitHub**: repo must be clean and portfolio-ready at all times from W1.

---

## 12. What Claude Code should NOT do

- Rename features (Tell Dwight, Ask Pam, etc. are final)
- Change the colour system or typography
- Add external JS frameworks without explicit go
- Skip docstrings
- Hardcode a single LLM provider or storage backend — all model/RAG calls go through swappable interfaces (revised July 2026). Sovereignty is the V2 product target, not a POC constraint.
- Hardcode character names or avatars in routes/UI — they live behind one swappable `character` config map (IP-safe rebrand hedge, see PRODUCT_ROADMAP.md)
- Generate placeholder UI that doesn't match the design system
- Make architecture decisions without surfacing them first
- Modify the data model without a dedicated session and explicit go
