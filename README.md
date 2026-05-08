# Scranton

> One smart notepad. Zero bureaucracy. 100% team.

A managerial OS for proximity managers in SMEs — local-first, Mistral-powered, anti-surveillance.

Inspired by the worst manager on American TV. Built for the best.

---

## What it does

Scranton captures the human layer that falls between every other tool — informal decisions, weak signals, verbal commitments, team mood. It structures silently, surfaces what matters, and never lets the manager become a bureaucrat.

The AI is never visible as a decision-maker. The manager remains the sole source of every human decision.

---

## POC features

| Feature | Description |
|---|---|
| **Tell Dwight** | Universal free-text input. Segments, routes, and reformulates notes automatically. |
| **Ask Pam** | Collective memory. Plain-language queries on your team's entire history. |
| **Pretzel Day** | 30-second daily mood check-in. 6-level palette from Flow to Danger. |

---

## Stack

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| API | FastAPI |
| LLM | Mistral API |
| Vector store | ChromaDB |
| Database | SQLite |
| Frontend | HTML / CSS / JS |

---

## Status

Pre-alpha. Data model validated. FastAPI skeleton in progress.

---

## Structure

```
backend/    FastAPI app, routes, Mistral integration
frontend/   HTML/CSS/JS interface
data/       SQLite database, ChromaDB store
tests/      Test suite
docs/       Feature documentation
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
