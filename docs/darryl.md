# Darryl the archivist - the documentary corpus serving Pam

> Built in the dedicated session of 2026-07-15 (data model included).
> The owner's arbitrations are recorded in `Pre-dev/product/BACKLOG.md`
> ("Darryl l'archiviste") and are not re-debated here.

## The doctrine

**Placing a document in the folder shared with Scranton IS its
validation.** That human gesture replaces the Dwight gate: Dwight
structures unstructured HUMAN input, nothing else. Two memories, one
Pam:

- **human layer**: notes -> Dwight -> explicit validation (unchanged);
- **documentary corpus**: shared folder -> Darryl -> Pam, directly.

Darryl is the invisible agent: narrow mandate (detect, extract, route,
version, index), no human decision to steal, no view of his own. His
trail is the archive strip inside the Pam overlay.

## The pipeline (`services/darryl_service.py`)

One `sync()` pass diffs the source against the corpus:

| Event | Effect |
|---|---|
| New file | extract, route, chunk, embed |
| Changed fingerprint (`content_sha256`) | re-extract and re-index; **routing kept** |
| Gone from the source | soft delete (`deleted_at`) + vectors dropped: removing a file withdraws the consent |
| Renamed / moved, same content | metadata follows silently |

Trigger: the **Sync button** in the Pam overlay strip (V1 decision: no
watcher, local-first, zero infra). `POST /api/v1/darryl/sync`.

### Routing: deterministic first, LLM second, never a bet

1. Folder path and file name are matched against the ACTUAL roster of
   clients and projects (normalized: case, accents, punctuation). This
   is the flexibility answer: no filing convention to configure - any
   company whose names appear somewhere in their tree routes for free.
   Match = tag at confidence 1.0, silently.
2. No match: the LLM reads title, path and an excerpt (closed world,
   roster injected) and proposes tags. Below
   `DARRYL_MIN_CONFIDENCE` (settings, default 0.75) or outside the
   roster: dropped.
3. No surviving tag: the **unclassified bin** (`status=unclassified`).
   Still queryable through Pam, feeds no entity file, correctable in
   one click from the strip (a `proposed_by=manager` tag replaces the
   routing - the Matthaeus lesson: never a plausible filing).

### Formats (`adapters/extraction/registry.py`)

pdf / docx / pptx / text / markdown are extracted and indexed; Google
Docs and Slides are exported as text at the Drive edge. **Spreadsheets
are cataloged, never extracted** (owner arbitration): one catalog chunk
(name, folder, date) keeps them findable by meaning. A corrupt file
catalogs instead of failing the sync.

### Versions

`family_key` = title normalized with version markers stripped
(`Rapport_SEO_final_V3_DEF(1).pdf` -> `rapport seo`; 4-digit years are
KEPT: `Bilan 2025` and `Bilan 2026` are different documents). The most
recent living member of a family carries `is_latest` and answers by
default; the others surface only through the deterministic
"all versions" Pam route. Heuristic by design: the worst case is two
versions answering - correctable, never blocking.

## Storage invariants

- SQLite is the source of truth for text: `documents`,
  `document_chunks`, `document_tags` (see `SCRANTON_CONTEXT.md` section
  5). Answers re-read chunks from SQLite, never from the index.
- The vectors live in a SECOND Chroma collection (`documents`), scalar
  metadata only (`chunk_id`, `document_id`, `data_type: cold`) and
  STATIC: routing, versions and deletion are applied at the SQLite
  re-read, so re-filing a document or a new version landing never
  re-embeds anything.
- The corpus is cold by construction: Pam's cold-only rule extends
  naturally, nothing warm can enter through a folder.

## One Pam, two memories (`services/pam_service.py`)

A question embeds once and queries both collections; the answer weaves
the best excerpts (sorted by score, capped at k, then numbered).
Sources are badged **team memory** / **document**; document sources
carry `title` and `link` (`web_view_link` - Fabrice's request number
one). The retrieval floor (`PAM_MIN_SCORE`) and the cited-only filter
apply to both memories. Prompt-side, each excerpt is labeled
`[team memory]` or `[document: <name>]` (rule 7 of Pam's prompt).

Deterministic routes, no LLM:
- "toutes les versions" / "all versions" naming a known family: the
  catalog of that family, newest first, links included.

## Sources (`adapters/documents/`)

`DocumentSource` seam, distinct from the Dwight-gate `IngestionSource`:

- `local.py`: walks a directory tree (the sovereign path and the test
  workhorse). `DARRYL_SOURCE=local`, `DARRYL_LOCAL_DIR=/path`.
- `gdrive.py`: walks the shared Drive folder RECURSIVELY, reusing the
  existing read-only OAuth material (one consent covers both
  connectors). `DARRYL_SOURCE=gdrive` (default) + the existing
  `GDRIVE_FOLDER_ID`.

Notion, Teams, Slack and GMail are later adapters on this seam. For
mail the owner's validated principle (2026-07-15): a mailbox is private
by nature, so each user shares their own fraction (candidate gesture: a
"Scranton" label) - the first flow where team members feed the
documentary memory directly.

## Surface (frontend, Pam overlay)

The strip under the Pam sheet head became the HISTORY strip (owner,
2026-07-15): the five last Dwight notes (raw note snippet + a
`validated/total` segment counter) ABOVE the five last ingested
documents (routing badges, `older version` chip, link when there is
one), the bin behind a one-line toggle, the one-click "file it" picker
(closed world: known clients and projects), and the Sync button. One
"Show more" button unfolds 10 more of EACH memory (endpoints
`/dwight/entries/recent` and `/darryl/documents/recent`, limit +
offset); reopening the overlay folds back to 5. Any strip error hides
it and never blocks Pam.

## Demo

The seed plants four corpus documents: a Prince Family Paper version
family (only the DEF answers by default), a cataloged spreadsheet
routed to Lackawanna, and one bin item to file. The former seed member
Darryl is now **Val** (same warehouse, different foreman): the
character key `darryl` belongs to the agent.
