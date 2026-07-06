# Smart Summaries — the six living templates (V1.3)

> Component doc, per the project QA standard: one .md per component.
> Code: `backend/app/services/summary_service.py` (registry + engine), `backend/app/services/llm_json.py` (shared JSON contract), `api/v1/summaries.py`.

## What it does

The six living templates from the product spec, powered by Dwight and
Pam together: auto-fed by capture, assembled from the validated memory
**on demand, never stored, never stale**.

| Template | About | Window |
|---|---|---|
| `team_member_file` | One member: skills, history, observations, signals | full history |
| `project_file` | One project: decisions, deliverables, people, open points | full history |
| `client_file` | One client: relationship, preferences, commitments | full history |
| `meeting_agenda` | Team-wide: topics, pending commitments, follow-ups | 30 days |
| `team_radar` | The manager 360: mood, weak signals, load | 30 days |
| `annual_review` | One member: a year of facts and discussion points | 365 days |

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/summaries` | Catalog: the templates + every pickable target, one call. |
| GET | `/api/v1/summaries/{template_id}?target_id=` | Assemble now. `404` unknown template/target, `422` missing target, `502` model contract failure. |

## Architecture (the part built to outlive the builder)

1. **Templates are data, not code.** The `TEMPLATES` registry declares
   id, title, target kind, section headings, window, view tags and
   context switches. The seventh template is a registry entry: no new
   code path, no new endpoint, no new prompt.
2. **Gathering is exhaustive SQL, not vector top-k.** A member file
   wants EVERYTHING about the member; semantic search would silently
   truncate it. Tags give exact membership; Chroma is for Pam's
   search, SQL is for assembly. Capped at the 60 most recent excerpts
   (the context says so when the cap bites), returned chronological so
   the model reads the story in order.
3. **One shared JSON contract** (`llm_json.complete_validated`): parse,
   validate against Pydantic, one retry with the failed answer in
   context. Dwight and Summaries use the same function, so the
   tolerance rules are tested once.
4. **Same gate as everywhere**: only VALIDATED segments feed a summary.
5. **Honest emptiness is free**: no material means every section reads
   "Nothing recorded yet." with zero completion tokens.
6. **People are never scored** - structural in the prompt (rule 6) and
   in the template wording: `annual_review` is explicitly *material*
   for the review, never a verdict.

Extra context beyond segments: the member templates inject the
member-owned human profile (labelled as such) and mood aggregates; the
radar injects team mood data. All marked as context lines, cited
material stays the excerpts.

## Known limitations (tuning pass material)

- mistral-small sometimes answers in English over French excerpts
  despite the dominant-language rule (observed live with a single
  excerpt); part of the deferred tone/relevance tuning pass.
- `meeting_agenda` gathers three views (agenda, CR, commitment) over a
  fixed 30-day window; per-meeting scoping (a real agenda for THE next
  meeting with client X) is a natural follow-up.
- Send Angela (one-click export) will consume `SummaryResponse` as-is.

## Testing

`tests/test_summaries.py`: registry completeness, gathering rules per
template kind (entity tags, view tags + window, warm layer for the
radar), profile + mood context injection, the free empty path, the
error contract, and the HTTP surface. Verified live: Kevin's member
file assembled by the real model with grounded citations and honest
empty sections.
