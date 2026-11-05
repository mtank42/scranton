# Scranton

> One smart notepad. Zero bureaucracy. 100% team.

A managerial OS for proximity managers in SMEs: privacy-first, Mistral-powered, anti-surveillance.

Inspired by the worst manager on American TV. Built for the best.

---

## What it does

Scranton captures the human layer that falls between every other tool: informal decisions, weak signals, verbal commitments, team mood. It structures silently, surfaces what matters, and never lets the manager become a bureaucrat.

Under the hood, Scranton is a team of **specialized agents** (Dwight captures and routes, Pam remembers, Toby watches over team health, Angela exports) sharing one memory and **orchestrated by the manager**, never the other way around. Where the market sells autonomous agents that decide for you, Scranton's agents propose and the human validates. Human-orchestrated agency is the product thesis, not a limitation.

The AI is never visible as a decision-maker. The manager remains the sole source of every human decision.

---

## POC features

| Feature | Description |
|---|---|
| **Tell Dwight** | Universal free-text input. Segments, routes, and reformulates notes; the manager validates. |
| **Ask Pam** | Collective memory over TWO sources - the validated human layer and the document corpus - plain-language queries, grounded answers with cited, openable sources. |
| **Darryl the archivist** | A shared folder IS consent: Darryl syncs, extracts, routes silently (unclassified bin, never a bet), versions files, and feeds Pam. In-app preview for every document. |
| **Michael's Desk** | The manager's workbench: living briefs (1:1, agenda, radar, annual review) and **document editing** - one canvas, edits by hand or with Dwight, computed diffs, undo, Save as the only persisting gesture. |
| **Pretzel Day** | 30-second daily mood check-in. 6-level palette from Flow to Danger. |
| **Meet Toby** | Team health overview: mood trends and weak signals. Facts, never scores. |
| **That's What She Said** | Completion reward. A random quote on every validated segment or check-in. (Paused with the Maire pending the celebrations overhaul.) |
| **Google Drive ingestion** | Both gates - Dwight's capture pipeline and Darryl's corpus - plug into Drive (one-time OAuth setup). |
| **Human profile** | Member-owned personal profile ("what they love"), declared through their own space. |
| **Maire de Scranton** | On their birthday, a member runs the town for 24 hours. The manager gets a week's notice, interests included. |
| **Smart Summaries** | Six living templates (member, project, client, agenda, radar, annual review) assembled from the memory on demand. |
| **Send Angela** | One-click export of any summary (.md, printable .html). No retyping. No questions asked. |
| **Transfer to Philly** | GDPR-aligned handover: cold facts + selected warm observations, verbatim, employee-reviewable. |

---

## Stack

| Layer | Choice |
|---|---|
| Language | Python 3.12 |
| API | FastAPI |
| LLM | Provider-agnostic via `LLMProvider` (Mistral default, Gemini fallback) |
| Vector store | ChromaDB (behind a `VectorStore` interface) |
| Database | SQLite (SQLAlchemy ORM) |
| Frontend | HTML / CSS / JS |

---

## Status

Pre-alpha, moving through the rebuilt roadmap
([Pre-dev/product/PRODUCT_ROADMAP.md](Pre-dev/product/PRODUCT_ROADMAP.md) §4)
with one dedicated owner session per chantier and a sliding-scope QA
checklist between them. 201 offline tests keep it honest.

**Done.** The 2026-07-12 realignment shipped in full: one OS, two roles,
the agents as ever-present actions
([Pre-dev/product/RECADRAGE_2026-07-12.md](Pre-dev/product/RECADRAGE_2026-07-12.md)).
On top of it, the two *indispensable* chantiers: **Darryl the archivist**
(the document corpus behind Pam: silent routing, version families,
unclassified bin, in-app preview; [docs/darryl.md](docs/darryl.md)) and
**document editing** (a surface-independent engine and a standard-model
editor: one canvas, computed diffs, undo, Save as the only persisting
gesture; [docs/document_editing.md](docs/document_editing.md)). Four owner
QA passes drove the polish; only the real-Drive QA section remains open.

**Done too (2026-07-18).** Manager identity, admin role & team
onboarding, the privacy-first pivot: Scranton is a client-server web
app, every person logs in from their own machine. Real accounts
(argon2id), a styled landing, server-side scoping of every surface,
and an Admin view where the manager creates the team (provisional
password shown once, first login forces a change);
[docs/identity.md](docs/identity.md).

**Next.** Oscar (the operations board) and exports & sharing.

---

## Getting started

**macOS shortcut**: double-click `Scranton.app` at the repo root (or drag it
to the Dock). It starts the local server if needed, reuses it otherwise, and
opens the app at `http://127.0.0.1:8001`. The bundle resolves paths relative
to itself: keep it inside the repository, do not copy it to /Applications.

**Owner QA**: double-click `Scranton QA.command`: it boots a throwaway
environment under `data/qa/` (your real data is never touched), reseeds the
demo dataset, and opens an interactive checklist at `localhost:8010/qa.html`.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then add your API keys

uvicorn backend.app.main:app --reload    # http://127.0.0.1:8000/docs
pytest                                   # offline test suite, no API key needed

# Optional: load the Dunder Mifflin demo dataset (3 months of history,
# real embeddings at seed time - needs MISTRAL_API_KEY in .env).
# The seed also creates the demo accounts and prints their credentials
# (michael@dundermifflin.com is the manager). A FRESH database shows
# the first-run setup screen instead: create your own manager account.
python -m backend.app.db.seed --reset    # --reset wipes db + vector index first

pytest -m integration                    # real-API smoke tests + golden Ask Pam queries
```

---

## Structure

```
backend/            FastAPI app, routes, provider-agnostic LLM integration
frontend/           HTML/CSS/JS interface
data/               SQLite database, ChromaDB store
tests/              Test suite
docs/               Feature documentation
Pre-dev/product/    Product source of truth: context, roadmap, backlog
Pre-dev/pitch/      Slides, 2-pager, storytelling, design assets
```

---

## About

Built by Mathieu Tank, 25+ years in digital Product, Ops, and Editorial.
Currently at École 42, learning Python and AI from scratch.
This project is the portfolio.

> A 25-year digital manager came back from École 42 at 56,
> learned Python and AI from scratch,
> and built his own management OS.
> Privacy-first. Mistral-powered. Anti-surveillance.
> Demo available on request.
