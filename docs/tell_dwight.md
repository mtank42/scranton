# Tell Dwight — capture engine (M1)

> Component doc, per the project QA standard: one .md per component.
> Code: `backend/app/services/dwight_service.py`, `backend/app/services/prompts.py`, `backend/app/api/v1/dwight.py`.

## What it does

Tell Dwight turns a messy free-text note into structured, routed memory:

```
raw note -> entries (immutable)
         -> LLM: segment + reformulate + classify + propose tags
         -> entry_segments (proposed) + segment_tags (proposed_by=dwight)
         -> manager validates/rejects each segment
         -> VALIDATED segments only: embed -> ChromaDB (Ask Pam's memory)
```

The AI proposes, the manager decides. Nothing enters the collective memory
without an explicit validation.

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/dwight/entries` | Submit `{raw_content, source_type?, submitted_by_id?}`. Returns the persisted entry with proposed segments, or a clarifying question. `201`. |
| POST | `/api/v1/dwight/entries/{id}/reply` | Answer Dwight's clarifying question (`{message}`). Reprocesses with the answer as context; may return another question (the thread continues). `200`, `404`, `409` if the entry is not pending. |
| POST | `/api/v1/dwight/segments/{id}/validate` | Submit `{status: "validated" \| "rejected"}`. Returns the updated segment. A plain reject is also the 'Forget it' exit of the rework loop. `200`, `404`. |
| POST | `/api/v1/dwight/segments/{id}/rework` | Reject with a comment (`{comment}`); Dwight proposes a corrected segment at the same position. Loops until validation or 'Forget it'. `200`, `404`, `409` if already decided. |

Error contract: a model failure returns `502` and the raw entry is already
saved with `processing_status = pending` — the note is never lost.

## The dialogue (M3.6, owner feedback on the first demo)

Clarification and rejection are conversations, not dead ends:

- **Vague note** → Dwight asks one question, displayed as a message
  thread in the UI; the manager answers inline and the segmentation
  resumes with that context. Dwight may ask again.
- **Rejected proposal** → the manager says what is wrong; Dwight comes
  back with a corrected segment (the rejected row stays as audit trail,
  the replacement takes its position). The loop runs until validation,
  with a 'Forget it' escape (plain reject, definitive).
- **No thread persistence** (owner decision 2026-07-06): only the raw
  note and the resulting segments count. Dialogue text feeds the model
  transiently and is not stored.
- Prompt rules added: the note is written by the manager in the first
  person; a clarifying question targets the missing INFORMATION, never
  who "I" is (the "Qui a réussi ?" bug, fixed and verified live:
  "J'ai réussi" now gets "Qu'avez-vous réussi ?").

## Design decisions (deliberate, revisit only with a reason)

1. **Embedding happens at validation, not capture.** The architecture
   sketch suggested embed-at-capture; indexing unvalidated proposals would
   let rejected content leak into Ask Pam's answers. Validation is the
   gate to the vector store. Rejected segments stay in SQLite as audit
   trail but never reach Chroma.
2. **Clarification is stateless.** If the note is too vague, Dwight
   returns one question, the vague entry stays `pending` (immutable audit
   trail), and the manager submits a richer note as a new entry. No
   conversation state to persist in the POC.
3. **One formatting retry.** If the model answer is not valid JSON, the
   failed answer is sent back with a reminder, once. Second failure = 502.
   Markdown ```json fences are tolerated and stripped before parsing.
4. **Entity tags are closed-world.** The prompt receives the actual roster
   (team members, clients, projects, stakeholders) with ids; Dwight may
   only tag entities from that list. Unknown names are simply not tagged
   (entity creation from notes is a later concern).
5. **Chroma metadata is flattened to scalars.** Chroma refuses list
   values, so tags become boolean keys: `team_member_3: true`,
   `view_commitment: true`, plus `data_type`, `sensitivity_level`,
   `entry_id`. Ask Pam (M2) filters on these keys.
6. **LLM output goes through Pydantic** (`DwightProposal`): a malformed
   proposal fails loudly at the edge instead of corrupting the database.

## Testing

- `pytest` — offline. The pipeline is tested against `ScriptedLLMProvider`
  (tests/conftest.py): tests script the model answer, then assert on what
  was persisted/indexed/refused.
- `pytest -m integration` — real Mistral smoke tests (auth, request shape,
  response parsing). Needs `MISTRAL_API_KEY` in `.env`.
- Verified end to end on 2026-07-06 with `mistral-small-latest`: a messy
  French note was segmented in 3, reformulated, classified cold/warm with
  sensible sensitivity, and routed to the right entities and views.

## Known limitations / next steps

- `mistral-small-latest` reports `confidence: 1.0` on everything: the
  confidence signal is not yet discriminating. Candidates: prompt tuning,
  or model escalation (small -> medium) once quality is measurable.
- No reprocess endpoint for a `pending` entry yet (after a 502 or a
  clarification): re-submitting a new note is the POC workaround.
- Cold/warm boundary needs golden-set evaluation (a repeated mistake was
  classified cold/2; warm/3 is arguable). Planned with the anti-regression
  golden queries when Ask Pam lands (M2).
