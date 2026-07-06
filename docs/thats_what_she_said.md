# That's What She Said — completion reward (M3.4)

> Component doc, per the project QA standard: one .md per component.
> Code: `frontend/app.js` (twss + TWSS_QUOTES), `frontend/styles.css` (#twss).

## What it does

A visual reward on completion moments: a full-screen overlay with a
random Michael-Scott-flavoured line, auto-dismissed after ~3 seconds
(or on click). The cheap delight of the MLP - the "L" garnish.

## Triggers (owner rules, 2026-07-06, second iteration)

1. **End of a Dwight report** = every segment decided, whatever the mix
   of validates and rejects. Then:
   - **First report of the day** (no check-in recorded today): the
     inline Pretzel Day panel appears instead; the reward fires ONLY if
     a mood is actually given. 'Rather not say' = no reward.
   - **Later reports**: the reward fires directly.
2. A Pretzel Day **check-in is recorded** (inline panel or standalone
   screen).

Rationale (owner): reporting is tedious but mandatory; talking about
how you feel is delicate and optional. Pretzel Day rides on the report
so it is never neglected, and the reward nudges the mood answer.

## Backlog

Mood-adaptive rewards (owner idea, in BACKLOG.md): the reward content
should match the declared mood - no cheap joke for someone Not okay
(a cute cat instead), a legendary football goal for someone In the
zone.

## Design decisions

1. **The quotes are original**, written for this demo in the style of
   the character - not verbatim show lines (IP caution, PRODUCT_ROADMAP
   section 8). The signature reads "- Michael Scott, probably".
2. **Frontend-only feature**: no backend surface, no persistence. The
   quote pool is a JS array; per-user customisation is a V1+ concern.
3. Pure CSS pop animation; the overlay explicitly restates
   `#twss[hidden] { display: none }` because an author `display: grid`
   would otherwise defeat the `hidden` attribute (learned live).

## Emoji note

The context allows emoji in UI only for this feature; the current
version needs none - the overlay carries the delight on its own.
