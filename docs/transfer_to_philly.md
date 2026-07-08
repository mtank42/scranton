# Transfer to Philly — handover, case 1 core (V1.5)

> Component doc, per the project QA standard: one .md per component.
> Code: `backend/app/services/handover_service.py`, `backend/app/adapters/export/handover.py`, `backend/app/api/v1/handover.py`.
> Status: the **core** ships (dossier, selective disclosure, portable contract, signable fiche). The validation **traceability** (`handover_validations` table) awaits a dedicated data model session — full proposal at the end of this doc.

## What it does

When a team member moves to another team, the manager assembles a
handover dossier — the GDPR differentiator of the product:

- **Cold data** (objective facts): transmissible a priori, never filtered.
- **Warm data** (manager observations): sensitivity-sorted for review;
  the manager selects what to disclose. What is withheld travels as a
  COUNT, never as content — the receiving side knows something was
  withheld, not what.
- **Member-owned data** (human profile, birthday, mood history): never
  in a handover, structurally. It belongs to the member, who discloses
  to whom they choose.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/handover/{member_id}?include_warm=` | The portable dossier (JSON). Absent param = review state (all warm shown). `404` unknown member. |
| GET | `/api/v1/handover/{member_id}/export?format=md\|html&include_warm=` | The printable, signable fiche as a download. `422` on unknown format or malformed selection. |

`include_warm` is ONE comma-separated param, deliberately: a repeated
param cannot express an empty list on the wire (it just vanishes), so
"disclose nothing" would collapse into "show everything". With a single
string param the three states stay distinct: absent → review; `''` or
`'none'` → withhold all; `'3,7'` → disclose exactly those.

## Design decisions (the ones that must not drift)

1. **Deterministic, no LLM.** A GDPR consent artifact carries the exact
   validated segments, **verbatim** — never a model paraphrase. The
   service has no LLM seam and no vector store.
2. **Only VALIDATED segments**, the same single gate as Ask Pam, Toby
   and Summaries.
3. **Portable contract, versioned from day one** (sketch §13, the
   portability axis): `HandoverDossier` carries
   `schema_id = "scranton.handover.member"` and `schema_version = 1`.
   Case 2 (V2) makes two Scranton instances exchange this document;
   its shape is a promise. Bump the version only with a migration note
   here.
4. **Paper-level validation for now**: the printed fiche ends with a
   two-party signature block (outgoing manager + team member). This is
   a deliberate placeholder until `handover_validations` exists — not
   the final audit trail.
5. **UI is one link** on each Team card ("Transfer to Philly", opens
   the printable review-state fiche). The full review → select →
   confirm flow arrives with the validation workflow (see below).

## The data model session — dossier for the owner

Everything below touches the frozen data model and therefore waits for
an explicit session. Decisions to bring:

### `handover_validations` (proposed shape)

| Column | Purpose |
|---|---|
| `id` | PK |
| `team_member_id` | FK — who the handover is about |
| `status` | `proposed` → `employee_reviewed` → `both_validated` → `sent` |
| `disclosed_warm_ids` | the frozen selection (JSON text) |
| `created_at`, `reviewed_at`, `validated_at`, `sent_at` | one timestamp per state transition |
| `manager_signature`, `member_signature` | see question 1 |

Adding the table is cheap once decided: `init_db` uses `create_all`,
which creates missing tables without touching existing ones — no
migration tooling needed.

### Questions to decide

1. **Signatures or boolean?** A boolean is trivial; typed name +
   timestamp is a reasonable POC middle ground; a content hash is the
   strong version. Recommendation: typed name + timestamp now, hash
   with case 2.
2. **Snapshot or re-derivation?** Segments can change after validation
   (rework, new captures), but a handover is a point-in-time consent.
   Recommendation: freeze `disclosed_warm_ids` + a SHA-256 of the
   rendered fiche at `both_validated`; the fiche file itself is the
   artifact both parties signed.
3. **Who triggers `sent`?** Angela delivering (export downloaded) or an
   explicit manager action? Recommendation: explicit action — a
   download is not a transmission.
4. **Case 2 constraints (V2, decide nothing now)**: batch fiches per
   member, the outgoing manager's right to purge their own warm data
   (soft-delete with `deleted_by_manager_at`, never physical), and the
   ChromaDB export subset. The versioned contract above is the early
   insurance; nothing in it forecloses these.

## Testing

`tests/test_handover.py` — fully deterministic: cold/warm split and
sensitivity sort, member-owned data never leaks (asserted on the JSON
dump), selective disclosure with withheld count, disclose-nothing on
the wire, verbatim + signature block in markdown, HTML escaping, and
the endpoint error contract.
