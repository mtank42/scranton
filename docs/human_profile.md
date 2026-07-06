# Human profile — "what they love" (V1.1)

> Component doc, per the project QA standard: one .md per component.
> Code: `backend/app/services/team_service.py`, `backend/app/api/v1/team.py`, profile extraction in `dwight_service.py` + `prompts.py` (task 5).

## What it does

Each team member has a personal profile next to the professional one:
interests, passions, favorites, birthday. Not an HR form - what you
would know about a colleague after three months of truly listening.
This is the feature that feeds Maire de Scranton (V1) and the social
fabric answer to the Helio founders-vs-newcomers problem (BACKLOG.md).

## The ownership split (the product's foundation)

Professional data belongs to the manager. The personal profile and the
birthday belong to the TEAM MEMBER. In the POC (no auth) the manager
records on the member's behalf; in V2 each member edits their own
profile directly, and discloses only what they choose. Nothing in the
profile is ever used to score anyone.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/team/members` | Active roster with profiles (manager-only POC). |
| PUT | `/api/v1/team/members/{id}/profile` | Replace the member-owned fields `{personal_profile, birthday}` (null clears). `404` on ghosts. |

## Dwight extraction (consent-preserving)

When a note reveals personal-life information about a known team member
("Kevin m'a dit qu'il est né le 11 février et qu'il est fan de New
Order"), Dwight adds a **profile suggestion** to the capture response.

- Suggestions are **transient**: never persisted, never auto-applied.
  The manager explicitly adds them to the profile (append, not
  overwrite) or dismisses them - same consent gate as segment
  validation.
- **Closed world**: suggestions about unknown members are discarded.
- **No invented years**: small models fabricate a birth year from a
  partial date. If the suggested year is not literally present in the
  raw note, the server drops the birthday and keeps the fact in text
  (guard verified live: "né le 11 février" -> birthday null).
- Suggestions never hold a report open (they do not block the end-of-
  report reward or the inline Pretzel Day panel).

## Provisional decisions (to confirm in a product session)

The two open questions from PRODUCT_ROADMAP section 9 got the minimal,
reversible answers to keep V1 moving:

1. **Free text, not a structured table** - it is what the schema
   already had, and natural to type. The structured version (enabling
   Pam correlations like "two people love jazz") stays open.
2. **Extraction is systematic but consensual** - Dwight always
   proposes when he spots personal info; nothing lands without an
   explicit manager action. The alternative (on-demand only) stays
   open if this feels too eager in practice.

## Testing

`tests/test_team.py` (roster, PUT roundtrip incl. clearing, 404) and
the suggestion tests in `tests/test_dwight_service.py` (name
resolution, ghost filtering, year guard). Verified live end to end:
extraction -> Add to profile -> Team screen.
