# Identity, admin & onboarding - who enters Scranton, and as whom

> Built in the dedicated session of 2026-07-18 (data model included).
> The owner's arbitrations are recorded in `Pre-dev/product/BACKLOG.md`
> ("Identité du manager, rôle admin & onboarding d'équipe") and are
> not re-debated here.

## The doctrine

**Privacy-first, not local-first anymore** (owner, 2026-07-18): every
person reaches Scranton from their own machine and PROVES who they are
- a login per profile, manager and members alike. The POC's role
switch and identity picker are gone: **the session is the identity**,
and every surface's audience is enforced by the server, not by a
button.

The MVP deployment stays self-hosted on a team machine (documented
limit: if that machine sleeps, Scranton is closed for the team), but
the code is written like a plain web app - config by environment,
HTTPS-ready (`SESSION_COOKIE_SECURE`), nothing assumes localhost - so
a hosted instance is a deployment decision, not a rewrite.

## The data model (rule 2 slot, validated 2026-07-18)

Two NEW tables, zero modification of the existing thirteen:

- **`users`** - the accounts. The email is BOTH the login and the
  roster's only contact field (owner: "mail seul"). The manager is a
  user WITHOUT a roster row (`team_member_id` NULL): his "identity
  apart" (owner, 2026-07-14) is this shape, not a separate table, so
  the future co-admin is a role value, never a data move. He carries
  his own `full_name` and `birthday` (day + month, year erased -
  eligible Maire de Scranton, NO mood tracking).
- **`sessions`** - the logged-in browsers. The cookie carries an
  opaque random token; the database stores its SHA-256 only, exactly
  like passwords store an argon2id hash: a stolen database logs nobody
  in. Sessions last 30 days (`SESSION_TTL_DAYS`, owner's
  comfort-over-friction arbitration; logout and deactivation are the
  mitigations) and are REVOCABLE: logout, account deactivation and
  password changes kill them server-side.

## The flows

**First run** (`POST /auth/setup`): an empty base shows the setup
screen; creating THE manager account closes the door for good (409
afterwards). The founder flows straight into a logged-in session.

**Onboarding a member** (Admin view, manager-only): one gesture
creates the roster row and the account, and returns a **provisional
password shown exactly once** - never stored in clear, never logged,
never shown again. The admin passes it on out-of-band (no mail
infrastructure by design); the first login forces the member to
replace it (`must_change_password`). The same one-time display serves
the reset-password path and the migration path (giving an email to a
pre-identity roster row creates its account).

**Departure**: deactivation flips `is_active` (rows are never
deleted), cuts login immediately AND revokes every open session in
the same commit. Reactivation reopens login; dead sessions stay dead.
The data follows the handover doctrine, untouched.

## The scoping map (enforced in `api/deps.py`)

| Guard | Perimeter |
|---|---|
| none (public) | `/auth/status` `/auth/setup` `/auth/login`, `/config/ui` (branding for the landing), `/health` |
| `get_current_user` | Pam Q&A, summaries CATALOG (the UI's entity labels), `/team/mayor`, `/team/members` (shaped: members see names, the manager sees full rows), own mood history |
| `require_member` (self only) | Pretzel Day check-in (always your own), personal profile writes (owner-only - the manager-on-behalf era ended with the POC) |
| `require_manager` | Dwight, Toby, Darryl, edited documents, handover, Angela, ingest, summary generation, the Admin surface |

Member capture through Dwight is a V2 story (entries carry no author
today; the validation gate is the manager's gesture) - the Tell
Dwight button simply does not render for a member session.

## The surfaces

- **Landing + login**: one screen worded from the deck's cover (the
  UX compass) - brand column (Management OS, the notepad tagline, the
  cast from the character map: the rebrand seam holds here too) next
  to the entry card. Three form modes: login, first-run setup, forced
  password change.
- **Admin** (fourth manager tab): the roster with account status
  (departures stay listed), create / edit / deactivate / reactivate /
  reset password, and the one-time password notice.
- **Topbar**: the session chip (name + Log out) replaces the role
  switch and identity picker.

## Settings

| Variable | Default | Meaning |
|---|---|---|
| `SESSION_TTL_DAYS` | 30 | session lifetime (owner arbitration) |
| `SESSION_COOKIE_SECURE` | false | true on any HTTPS deployment |

## Deferred (recorded, not forgotten)

- **Co-admin** (owner: "later") - a `UserRole` value away, no
  migration needed.
- **HTTPS / hosted deployment** - the cloud discussion stayed open at
  the session; the MVP is the self-hosted option 1.
- **Member capture and member-validated segments** - V2 multi-user
  story.
- **Smartphone access** - "un futur plus lointain" (owner).
