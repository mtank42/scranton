# Ask Pam — memory engine (M2)

> Component doc, per the project QA standard: one .md per component.
> Code: `backend/app/services/pam_service.py`, `backend/app/services/prompts.py`, `backend/app/api/v1/pam.py`, `backend/app/adapters/vectorstore/chroma.py`.

## What it does

Ask Pam answers plain-language questions over the validated collective
memory, grounded and sourced:

```
question -> embed (LLMProvider)
         -> ChromaStore.query: top-k nearest validated segments (cosine)
         -> re-read segment text from SQLite (source of truth)
         -> LLM: answer grounded ONLY in those excerpts, cited [n]
         -> {answer, sources[]}
```

With M1 (Tell Dwight) this closes the MVP loop: capture proves nothing
without retrieval; together they prove nothing human is lost.

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/pam/query` | Submit `{question}`. Returns `{answer, sources[]}` where each source carries `segment_id`, `entry_id`, `content`, `data_type`, `sensitivity_level`, `score`, `created_at`. `200`; `422` on empty question. |

An empty `sources` list with the fixed no-memory answer is a valid,
honest `200` - not an error.

## Design decisions (deliberate, revisit only with a reason)

1. **No validation filter needed.** Only VALIDATED segments are embedded
   (M1 decision: validation is the gate), so the index cannot surface
   rejected or merely proposed content. The two engines share one
   invariant instead of each filtering defensively.
2. **SQLite wins over the index.** Chroma returns ids and scores; the
   text is re-read from SQLite. Hits whose ids are missing from SQLite
   are skipped; if all hits are ghosts, Pam answers "no memory" rather
   than answering from ghost content.
3. **Empty retrieval costs zero tokens.** No hits means a fixed, honest
   answer without a model call.
4. **No clarify step in M2** (the sketch marked it optional). Ambiguity
   is handled by the grounded prompt's honesty rules. A clarify
   round-trip can be added later without changing the API shape.
5. **Cosine space** for the Chroma collection (not the default L2):
   embedding similarity is directional. `score = 1 - cosine distance`.
6. **Prompt: partial beats nothing.** Tuned on the real model (see
   below): when the memory holds related but incomplete information,
   Pam reports what IS there and names the gap, instead of a bare
   "nothing". Includes a worked example - a bare rule was not enough
   for mistral-small.
7. **filters and k are service parameters, not API parameters** (yet):
   entity- or view-scoped queries (Smart Summaries, Meet Toby) will use
   them without a signature change.

## Prompt tuning log (2026-07-06, mistral-small-latest)

Empirical, per the roadmap's escalation policy (small -> medium -> Gemini
Flash only if measurably needed):

- "What did Kevin want to tell me?" first got a literal "I have nothing
  on what he wanted to say" although the memory held "Kevin asked to
  talk, call back Monday". mistral-medium gave the same literal answer,
  so this was a prompt problem, not a model-size problem: **no escalation**.
- Fix that worked: an explicit PARTIAL BEATS NOTHING rule plus a worked
  example. Quoted English phrases in the prompt anchored the answer
  language; replacing them with descriptions restored French answers.

## Testing

- `pytest` - offline. PamService runs against `ScriptedLLMProvider` +
  `FakeVectorStore` (scripted hits); ChromaStore is tested for real
  (local, no network): nearest-first order, metadata filters, $and
  semantics, upsert-overwrites-not-duplicates.
- Verified end to end on 2026-07-06 against the real API: partial-info,
  out-of-memory (honest refusal, no invention) and date questions all
  answered correctly in the question's language, with sources.

## Known limitations / next steps

- On out-of-memory refusals, mistral-small sometimes still appends
  cosmetic citations ([1, 2]) despite the no-source rule. Harmless
  (the text is honest) but worth a golden-set assertion later.
- The golden-query anti-regression set (SCRANTON_CONTEXT section 11)
  needs the seeded Dunder Mifflin dataset: planned with M3.
- `sensitivity_level` is not yet used to filter retrieval: single-manager
  POC shows everything to its only user. Becomes real with multi-user
  (V2) and Transfer to Philly (V1).
