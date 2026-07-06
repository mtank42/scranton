# That's What She Said — completion reward (M3.4)

> Component doc, per the project QA standard: one .md per component.
> Code: `frontend/app.js` (twss + TWSS_QUOTES), `frontend/styles.css` (#twss).

## What it does

A visual reward on completion moments: a full-screen overlay with a
random Michael-Scott-flavoured line, auto-dismissed after ~3 seconds
(or on click). The cheap delight of the MLP - the "L" garnish.

## Triggers (validated with the owner, M3 plan)

1. A segment is **validated** in Tell Dwight (something just entered the
   collective memory).
2. A Pretzel Day **check-in is recorded**.

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
