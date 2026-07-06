# Meet Toby v0 — team health overview (M3.1)

> Component doc, per the project QA standard: one .md per component.
> Code: `backend/app/services/toby_service.py`, `backend/app/api/v1/toby.py`.

## What it does

The payoff surface of the feel-better loop: mood trends per member and
team, plus weak signals, so the manager can act at week 6 instead of
week 14 (the Sonia trajectory from the product storytelling).

Toby aggregates and surfaces. It never scores, ranks or evaluates a
person - that line is the product's north star and it is structural in
this code: individual timelines are raw palette levels, and the only
average computed is a per-day team mood average.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/toby/overview?days=30` | `{window_days, generated_at, team_trend[], members[], signals[]}`. Manager-only (structural in the POC: single user). |

## The v0 signal catalog (validated with the owner, M3 plan)

| Type | Fires when | Detail example |
|---|---|---|
| `declining_mood` | The member's last three check-ins strictly worsen. | "Last three check-ins worsen: ctrl -> press -> stuck." |
| `low_mood` | Latest check-in is `stuck` or `danger`. | "Latest check-in is danger (2026-07-04)." |
| `sensitive_warm_segment` | Validated warm segments with sensitivity >= 4 about the member in the window. | "2 sensitive observations (level >= 4) recorded in the window." |
| `no_recent_checkin` | The member used to check in but has not for 7 days. Members who never checked in are excluded (a fresh roster must not open with a wall of alarms). | "No check-in for more than 7 days." |

Every signal is a dated fact the manager already had the right to see,
stated in neutral language. No severity score, no ordering of people.

## Design decisions

1. **No LLM in v0**: plain SQL aggregation. A later version may add
   model-written summaries on top, never model-made judgements.
2. **Thresholds are module constants** (`NO_CHECKIN_DAYS = 7`,
   `SENSITIVE_LEVEL = 4`): tunable in one place, no configuration
   surface until someone actually needs one.
3. **Signals recompute on every call**: no signal table, no state, no
   acknowledgement workflow in v0. The overview is a lens, not an inbox.

## Testing

`tests/test_toby.py`: one test per detector (including the
no-false-alarm cases: healthy member, never-checked-in member,
proposed-but-unvalidated sensitive segment), team trend averaging,
HTTP shape. No network needed.
