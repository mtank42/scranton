# Transfer to Philly — handover, case 1 (V1.5 core + V1.6 consent trail)

> Component doc, per the project QA standard: one .md per component.
> Code: `backend/app/services/handover_service.py`, `backend/app/adapters/export/handover.py`, `backend/app/api/v1/handover.py`.
> Status: **complete for case 1.** The core (dossier, selective disclosure, portable contract, signable fiche) shipped in V1.5; the validation traceability (`handover_validations` table) was decided in the dedicated data model session of 2026-07-08 and shipped in V1.6.

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
| GET | `/api/v1/handover/{member_id}/export?format=md\|html&include_warm=` | The printable fiche as a download — unsigned review material. `422` on unknown format or malformed selection. |
| GET | `/api/v1/handover/{member_id}/validations` | Every consent record for the member, newest first. |
| POST | `/api/v1/handover/{member_id}/validations` | Open a handover (`proposed`). Body: `{disclosed_warm_ids: []}`. `409` if one is already open, `422` on a non-disclosable id. |
| PUT | `/api/v1/handover/validations/{id}/selection` | Rework the selection — only while `proposed` (`409` after). |
| POST | `/api/v1/handover/validations/{id}/review` | `proposed` → `employee_reviewed`. |
| POST | `/api/v1/handover/validations/{id}/sign` | `employee_reviewed` → `both_validated`. Body: both typed names. Freezes `fiche_sha256`. |
| POST | `/api/v1/handover/validations/{id}/send` | `both_validated` → `sent`. Explicit manager action, never a download side effect. |
| GET | `/api/v1/handover/validations/{id}/export?format=md\|html` | The **signed** artifact (frozen selection, typed signatures). `409` before signature. Byte-stable for `md`: hashing the download reproduces `fiche_sha256`. |

Consent-trail error contract: not-found is `404`, a move the state
machine forbids is `409`, a bad selection is `422`.

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
4. **The consent trail is the validation** (since V1.6): the
   `handover_validations` table records who agreed to what, when. The
   fiche of a signed handover carries the typed signatures; the
   unsigned review export keeps blank paper lines.
5. **UI is the full workflow** on each Team card ("Transfer to Philly"
   opens the panel): review the warm observations → select → preview
   the fiche → "reviewed together" → both parties sign with typed
   names → download the signed fiche → "mark as transmitted".

## The consent trail — decided 2026-07-08 (data model session)

### `handover_validations` (the ninth table)

| Column | Purpose |
|---|---|
| `id` | PK |
| `team_member_id` | FK — who the handover is about |
| `status` | `proposed` → `employee_reviewed` → `both_validated` → `sent`, strictly forward |
| `disclosed_warm_ids` | the selection (JSON text). `'[]'` means "disclose nothing" |
| `fiche_sha256` | SHA-256 of the markdown fiche, frozen at signature time |
| `manager_signature_name`, `manager_signed_at` | typed name + timestamp |
| `member_signature_name`, `member_signed_at` | typed name + timestamp (separate columns so V2 can split the signing act) |
| `created_at`, `reviewed_at`, `validated_at`, `sent_at` | one timestamp per state transition |

The table was added through `create_all` (idempotent, creates missing
tables only) — no migration tooling, as planned.

### The three decisions (owner, 2026-07-08)

1. **Signatures: typed name + timestamp.** The POC middle ground; a
   per-signature content hash is the case 2 upgrade.
2. **Snapshot, not re-derivation.** A handover is a point-in-time
   consent: `disclosed_warm_ids` stops moving once the member reviews
   it (stricter than the minimum, so nothing changes under a signature),
   and `fiche_sha256` freezes at `both_validated`. The signed fiche is
   re-rendered byte-identically (`generated_at` pinned to
   `validated_at`); if the underlying segments were edited since, the
   bytes diverge and the hash exposes it — tamper evidence, by design.
3. **`sent` is an explicit manager action.** A download is a
   verification; a transmission is a decision. The export endpoints
   never mutate state.

**Case 2 constraints (V2, still open, nothing decided)**: batch fiches
per member, the outgoing manager's right to purge their own warm data
(soft-delete with `deleted_by_manager_at`, never physical), the
ChromaDB export subset, per-signature content hashes. The versioned
contract is the early insurance; nothing shipped forecloses these.

## Testing

`tests/test_handover.py` — fully deterministic: cold/warm split and
sensitivity sort, member-owned data never leaks (asserted on the JSON
dump), selective disclosure with withheld count, disclose-nothing on
the wire, verbatim + signature block in markdown, HTML escaping, and
the endpoint error contract. For the consent trail: the happy path,
strictly-forward transitions, selection frozen at review, selection
vetting (cold/foreign/ghost ids refused), one open handover per member,
byte-stable signed fiche whose hash matches `fiche_sha256`, and the
download-is-not-a-transmission guarantee.
