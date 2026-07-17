# Document editing - the manager's clean notebook

> Session 2026-07-16 (indispensable #2 of the roadmap). The manager
> finally owns what the engines generate: he saves a generation, edits
> it by hand or through Dwight, and the moving memory knocks with
> proposals instead of rewriting anything behind his back.
> **Surface redesigned 2026-07-17 (C3)** after the owner's QA verdict
> ("unusable from the second edit on"): the engine stayed, the editor
> became the standard model - one canvas, apply + undo, Save.

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
- Every edit carries a **computed diff** (difflib, word-level):
  insertions highlighted, deletions struck through. The model never
  self-reports its changes - the highlighting is guaranteed by the
  calculation, not by prompt discipline. Manual edits go through the
  same difflib (`POST /documents/diff`): one highlighting truth.
- **"Edit manually" lives beside "Edit with Dwight" everywhere**
  (owner decision, 2026-07-14): often the hand is faster.

## The editor surface (C3 redesign, owner arbitrations 2026-07-17)

The 2026-07-16 surface stacked up to three copies of the text
(document + Dwight proposal card + manual textarea) and each "Save and
edit" created a sibling document - the owner lost edits and called it
unusable. The C3 model, standard on purpose ("simple, intuitif, pas
depaysant"):

- **Two intentions, two buttons on every generated card**: "Save"
  keeps the generation as it is; "Edit" opens the editor on a DRAFT -
  the document is born at its first Save, wherever that Save happens
  (`POST /documents/revise` serves drafts, no id needed).
- **One canvas, full-frame in the Desk**: the open document replaces
  the Desk content ("<- My documents" to come back). Never two copies
  of the text on screen.
- **Apply + undo instead of propose + keep**: a Dwight revision, a
  manual Apply or a weave lands ON the canvas, highlighted vs version
  n-1 only. "Undo last edit" steps back one gesture per click
  (session-scoped stack, survives Save; the base keeps last state
  only). The doctrine holds: every version is born from a manager
  gesture, the document still never changes on its own.
- **Save is the only persisting gesture** and the status chip tells
  the truth (draft / unsaved changes / saved). Leaving with unsaved
  work asks first - in-app (view switches) and browser-level
  (beforeunload).
- Dwight always revises the CANVAS (unsaved edits travel via
  `content_md` in the revise body), and the weave advances the memory
  bookmark at Save time, decremented if the weave is undone.
- **A generation you saved reopens as YOUR document** (owner, QA v6):
  a Desk generate button whose template + target already has a saved
  document opens that document (delta panel included) instead of a
  fresh generation that would silently ignore the edits.
- Wording rule (owner, QA v6): sentences address the AGENT ('Edit
  with Dwight', 'What should Dwight change?'), buttons and tabs name
  the ACTION ('Tell Dwight'). `agent_name` in the characters map;
  never hardcode either. The weave button says 'Add with Dwight'.

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
