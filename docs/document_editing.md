# Document editing - the manager's clean notebook

> Session 2026-07-16 (indispensable #2 of the roadmap). The manager
> finally owns what the engines generate: he saves a generation, edits
> it by hand or through Dwight, and the moving memory knocks with
> proposals instead of rewriting anything behind his back.

## The doctrine

Templates stay LIVING - computed from the validated memory on demand,
never stored. The **first save is the human gesture** that turns one
generation into a persisted document (`edited_documents`). From then
on:

- The document **never changes on its own**. Reopened, it is the saved
  text, character for character.
- The gap with the moving memory is **presented, never applied**: the
  delta (validated segments about the target, newer than the
  `memory_reviewed_at` bookmark) arrives as proposals the manager
  triages by dialogue. What he leaves out is dismissed for good for
  THIS document - it stays in Pam's memory.
- Every Dwight revision is a **proposal with a computed diff**
  (difflib, word-level): insertions highlighted, deletions struck
  through. The model never self-reports its changes - the highlighting
  is guaranteed by the calculation, not by prompt discipline. Saving
  the proposal is a separate explicit gesture.
- **"Edit manually" lives beside "Edit with Dwight" everywhere**
  (owner decision, 2026-07-14): often the hand is faster.

## Dwight the pure reviser (owner arbitration, 2026-07-16)

"Option B is Dwight playing Pam." Dwight receives the current document,
the manager's instruction and the selected delta excerpts - the context
always travels - and returns the revised document. One
`complete_validated` call (`DwightRevision`), ZERO memory access of his
own. New content comes from the instruction or the selected excerpts;
fetching from memory is Pam's job, in her overlay.

## The engine is surface-independent

`services/editing_service.py` never knows which screen called it.
Today: Michael's Desk ("Save and edit" on any generated summary, the
"My documents" block) and the Pam template cards ("Save and edit" lands
on the Desk editor). Tomorrow: Oscar's entity files consume the same
routes. API: `POST /documents`, `GET /documents(/{id})`,
`POST /documents/{id}/save`, `GET /documents/{id}/delta`,
`POST /documents/{id}/mark-reviewed`, `POST /documents/{id}/revise`.

## The corpus entry and the person exception

An edited **client or project** document enters Darryl's corpus at each
save (owner decision: one notion of document in the product): a
`documents` row with `source='scranton'`, `origin_ref='scranton:<id>'`,
a manager tag at confidence 1.0 - the save gesture IS the filing, the
same doctrine as the shared folder. Content changes re-chunk and
re-embed through Darryl's changed-content path.

**Person-targeted documents (1:1 brief, annual review material) NEVER
enter the corpus**: people never flow through Pam (owner, QA
2026-07-14, reaffirmed 2026-07-16). They stay persisted, editable and
exportable - on the Desk, the manager-only surface.

`DarrylService.sync()` excludes `source='scranton'` rows from
reconciliation: a connector sync must never soft-delete documents that
were never the connector's to manage.

## Data model (validated 2026-07-16)

One table, `edited_documents`: `id`, `title`, `template_key`,
`target_entity_type/id` (nullable - team-wide templates have no
target and no delta), `content_md` (clean markdown, review highlights
are never stored), `generated_at`, `created_at`, `updated_at`,
`memory_reviewed_at`. **Last state only** (owner arbitration): no
version history in V1. `memory_reviewed_at` starts at `generated_at`
(the generation already gathered everything up to that moment).

The delta uses the segment's `created_at` as the proxy for "when it
entered the memory": validation has no timestamp of its own in the
validated data model, and capture-to-validation is minutes in practice.

## Frontend notes

- The editor renders `content_md` as native `<details>` sections split
  on `## ` headings: the accordion (fold a covered section during the
  1:1) for free, no library.
- The news panel checks every proposal by default; the weave
  instruction is optional (a sensible default instruction is sent).
- "Keep it" on a weave revision advances the bookmark in the same
  gesture; a plain instruction revision does not touch it.
