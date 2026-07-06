# Scranton

> One smart notepad. Zero bureaucracy. 100% team.

A managerial OS for proximity managers in SMEs — local-first, Mistral-powered, anti-surveillance.

Inspired by the worst manager on American TV. Built for the best.

---

## What it does

Scranton captures the human layer that falls between every other tool — informal decisions, weak signals, verbal commitments, team mood. It structures silently, surfaces what matters, and never lets the manager become a bureaucrat.

Under the hood, Scranton is a team of **specialized agents** — Dwight captures and routes, Pam remembers, Toby watches over team health, Angela exports — sharing one memory and **orchestrated by the manager**, never the other way around. Where the market sells autonomous agents that decide for you, Scranton's agents propose and the human validates. Human-orchestrated agency is the product thesis, not a limitation.

The AI is never visible as a decision-maker. The manager remains the sole source of every human decision.

---

## POC features

| Feature | Description |
|---|---|
| **Tell Dwight** | Universal free-text input. Segments, routes, and reformulates notes; the manager validates. |
| **Ask Pam** | Collective memory. Plain-language queries, grounded answers with cited sources. |
| **Pretzel Day** | 30-second daily mood check-in. 6-level palette from Flow to Danger. |
| **Meet Toby** | Team health overview: mood trends and weak signals. Facts, never scores. |
| **That's What She Said** | Completion reward. A random quote on every validated segment or check-in. |
| **Google Drive ingestion** | Pull a Drive folder through the same capture pipeline (one-time OAuth setup). |
| **Human profile** | Member-owned personal profile ("what they love"). Dwight suggests additions from your notes; you decide. |

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

Pre-alpha. **MLP code-complete (M3)**: the full demo loop runs in the browser — capture and validate with Tell Dwight, query the memory with Ask Pam, daily Pretzel Day check-ins, team trends and weak signals in Meet Toby, a That's What She Said reward on every completion. Seeded Dunder Mifflin dataset with golden anti-regression queries (5/5 against the real provider). Google Drive ingestion is wired and tested on mocks; its end-to-end run needs the one-time OAuth setup ([docs/google_drive_ingestion.md](docs/google_drive_ingestion.md)).

V1 in progress: **human profile shipped** (member-owned data, consent-preserving extraction). Next: Maire de Scranton or Smart Summaries, plus the tuning pass (agent relevance, tone, reward pacing).

---

## Getting started

**macOS shortcut**: double-click `Scranton.app` at the repo root (or drag it
to the Dock). It starts the local server if needed, reuses it otherwise, and
opens the app at `http://127.0.0.1:8001`. The bundle resolves paths relative
to itself: keep it inside the repository, do not copy it to /Applications.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then add your API keys

uvicorn backend.app.main:app --reload    # http://127.0.0.1:8000/docs
pytest                                   # offline test suite, no API key needed

# Optional: load the Dunder Mifflin demo dataset (3 months of history,
# real embeddings at seed time - needs MISTRAL_API_KEY in .env).
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

Built by Mathieu Tank — 25+ years in digital Product, Ops, and Editorial.
Currently at École 42, learning Python and AI from scratch.
This project is the portfolio.

> A 25-year digital manager came back from École 42 at 56,
> learned Python and AI from scratch,
> and built his own management OS.
> Local-first. Mistral-powered. Anti-surveillance.
> Demo available on request.
