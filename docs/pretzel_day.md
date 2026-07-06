# Pretzel Day — mood check-in (M3.1)

> Component doc, per the project QA standard: one .md per component.
> Code: `backend/app/services/mood_service.py`, `backend/app/api/v1/mood.py`.

## What it does

The 30-second daily ritual: one team member, one of six mood levels,
an optional free-text note. This is the most on-thesis feature in the
product: the raw material of the feel-better loop.

## The palette

| Level | Index | Colour (design system) | UI label (first-degree) |
|---|---|---|---|
| flow | 5 | `--green` #00C853 | In the zone |
| ctrl | 4 | `--cyan` #00D4FF | Under control |
| pretzel_day | 3 | `--purple` #7B61FF | So-so |
| press | 2 | `--yellow` #F5C518 | Under pressure |
| stuck | 1 | `--orange` #FF6D00 | Stuck |
| danger | 0 | `--red` #E63946 | Not okay |

The palette values are the data model vocabulary and never change; the
UI labels + emoji are display-only (owner feedback 2026-07-06: the raw
names were obscure at first read). The mood emoji are the explicit
exception to the no-emoji rule. A dedicated Pretzel Day icon is
pending: the owner provides the asset.

The index (`MOOD_INDEX` in `domain/models.py`) is ordinal and belongs
to the MOOD, never to the person: it exists so trends can be drawn.
No score of a human being is computed anywhere.

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/mood/checkins` | `{team_member_id, mood_level, note?}` -> `201`; `404` unknown member; `422` invalid level. |
| GET | `/api/v1/mood/checkins?member_id=&days=30` | History, oldest first. |

## Design decisions

1. **Attributed, not anonymous** (data model decision, May 2026): the
   trust model is the manager protecting the team's data, not the tool
   hiding the team from the manager.
2. **No LLM anywhere**: recording a mood is pure data entry. The note
   field is stored as-is; routing it through Dwight is a possible later
   enhancement, not a POC need.
3. **History is oldest-first** because every consumer (trend charts,
   Meet Toby) reads time left to right.

## Testing

`tests/test_mood.py`: service roundtrip, unknown-member error, HTTP
contract (201/404/422). No network needed.
