# Maire de Scranton — the birthday ritual (V1.2)

> Component doc, per the project QA standard: one .md per component.
> Code: `team_service.py` (mayor_overview, next_occurrence), `api/v1/team.py` (GET /team/mayor), `frontend/app.js` (loadMayor, ritualCard).

## What it does

On their birthday (day + month - the year does not exist in Scranton),
a team member is **Maire de Scranton for 24 hours**:

- A banner in the sidebar and a "maire today" badge on their Team card.
- The celebration overlay fires on its own on the day (purple variant
  of the reward stage, "By order of the Office of the Mayor").
- The manager gets the J-7 reminder: "X's birthday is in N days - want
  to prepare something with the team?" with the human profile along
  for inspiration (that is what the profile is FOR).

An annual, predictable, positive ritual. Zero bureaucracy.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/team/mayor` | `{mayor: member \| null, upcoming: [{member, in_days}]}` over a 7-day window. |

## Design decisions

1. **Computed on read, no scheduler.** The POC answer to the
   scheduling seam (ARCHITECTURE_SKETCH section 13): the overview is
   derived from the roster at request time. A real notifier (push,
   email) plugs in later without touching this logic.
2. **The office clock, not UTC**: a birthday is a calendar day for the
   people in the room.
3. **February 29 is celebrated on February 28** in non-leap years - a
   birthday every four years would be the opposite of a ritual.
4. **Members without a recorded birthday simply never appear**: giving
   the date is a disclosure choice (member-owned data), silence is
   respected.
5. The V1 'interface adopts their favorite colors' idea from the
   BACKLOG stays open: the badge/banner/overlay are the v0 of the
   24-hour spotlight.

## Demo dataset

The seed places Kelly's birthday on seed day (she is Maire during the
demo) and Darryl's three days later (the reminder shows). Relative
dates, like the rest of the dataset.

## Testing

`tests/test_maire.py`: mayor detection, reminder window bounds,
departed members excluded, no-birthday silence, year rollover
(December -> January) and leap-day handling, endpoint shape.
