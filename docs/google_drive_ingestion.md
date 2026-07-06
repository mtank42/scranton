# Google Drive ingestion (M3.5)

> Component doc, per the project QA standard: one .md per component.
> Code: `backend/app/adapters/ingestion/gdrive.py`, `backend/app/services/ingestion_service.py`, `backend/app/api/v1/ingest.py`.

## What it does

Pulls one configured Drive folder and runs every supported document
through the normal Tell Dwight pipeline: entries, proposed segments,
manager validation. There is exactly one capture path in Scranton;
Drive is just the first real connector behind `IngestionSource`.

Supported: Google Docs (exported as plain text) and text/markdown
files. Anything else (PDF, images) is skipped, never fatal.

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/ingest/gdrive` | Pull the folder. Returns `{documents, entry_ids, clarifications, failures}`. `503` with guidance when OAuth or the folder id is missing. |

## One-time setup (owner machine)

1. Go to https://console.cloud.google.com/ and create (or pick) a project.
2. Enable the **Google Drive API** (APIs & Services > Library).
3. Configure the OAuth consent screen (External, test mode is fine;
   add your own Google account as test user).
4. Create credentials: **OAuth client ID > Desktop app**. Download the
   JSON and save it as `data/google_client_secrets.json`.
5. Put the Drive folder id in `.env`: `GDRIVE_FOLDER_ID=<id>` (the last
   part of the folder URL).
6. First `POST /api/v1/ingest/gdrive` opens a browser for consent, then
   caches the token at `data/google_token.json`. Later runs are silent.

Both files live under `data/` and are git-ignored (`data/*.json`).

## Design decisions

1. **Read-only scope** (`drive.readonly`): the connector must never be
   able to modify the user's files.
2. **Installed-app OAuth flow**: right for a local-first single-user
   POC. A hosted consent flow becomes necessary only with V2 multi-user.
3. **Normalize at the edge**: Drive specifics stop at `RawDoc`. The
   ingestion loop and the pipeline are source-agnostic; the same
   `IngestionService` will serve WhatsApp exports or Apple Notes.
4. **Synchronous pull** for the POC (a demo folder holds a handful of
   files). The async 'in the truck' batch seam is V2.
5. **A failing document is counted, skipped, and its raw text is
   already safe** in `entries` (status pending) - nothing human is lost.
6. Privacy: Drive is a tester-onboarding convenience and the demo is
   explicit about it; sovereign/local ingestion is the V2 target.

## Testing

`tests/test_ingestion.py` - offline: the Drive client is replaced by a
fake (listing + export + get_media), the loop is tested on an in-memory
source with a scripted model, and the endpoint's 503 guidance is
asserted. End-to-end verification requires the owner's OAuth setup
above: not automatable in CI by design.
