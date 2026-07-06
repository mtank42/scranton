# Send Angela — one-click export (V1.4)

> Component doc, per the project QA standard: one .md per component.
> Code: `backend/app/adapters/export/` (the Exporter seam), `services/angela_service.py`, `api/v1/angela.py`.

## What it does

One click on an assembled Smart Summary and Angela delivers the file.
No retyping, no questions asked.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/angela/export/{template_id}?target_id=&format=md\|html` | Assemble the summary now and download it. `404`/`422`/`502` follow the summary error contract; unknown format is a `422` naming the available ones. |

GET on purpose: an export is a read, and a plain `<a download>` link in
the UI (or a curl) is the whole client Angela needs.

## The Exporter seam (ARCHITECTURE_SKETCH section 13, Output axis)

Formatting never happens inside services. `Exporter.render(summary) ->
ExportFile {filename, media_type, content}` is the seam; formats live
in a registry (`EXPORTERS`). Adding PDF generation, Grist Core or Docs
(LaSuite) is one adapter plus one registry entry - Angela's logic and
the endpoint never change.

POC formats, zero dependencies:

- **`.md`** - the universal format: pastes into mail, Notion, Docs, a
  ticket. Title, provenance lines, sections as headings, numbered
  dated sources with their cold/warm marker.
- **`.html`** - a standalone printable page (white paper, IBM Plex,
  print-friendly): open, Cmd+P, and that is the POC's PDF. Everything
  model- or user-authored is escaped before it touches markup.

Filenames are tidy and sortable: `scranton_<template>_<target>_<date>.<ext>`.

## Design decisions

1. **Angela owns nothing**: she calls the summary engine (same
   validation gate, same sources) and an exporter. Living documents
   are assembled at export time - an export is always current.
2. **UI is two links** under the assembled summary, labelled from the
   character map (never hardcoded), with Angela's avatar.
3. The V2 backlog items (send-to-recipient for Transfer to Philly,
   billing connector, Grist) will extend the registry, not the flow.

## Testing

`tests/test_angela.py`: markdown structure, HTML escaping of hostile
content, slug/filename helpers, unknown-format error, and the HTTP
delivery (attachment headers, honest empty export, error codes).
Verified live: Kevin's member file downloaded as .md through the UI
link.
