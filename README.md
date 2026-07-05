# EventFlow

Invitation/guest management and seating for large recurring conferences.
This repo currently implements:

- **Module 1: Golden Record** (`people`) - a stable person identity
  (`person_id`) with fuzzy duplicate detection every other module refers to.
- **Module 2: Nomination & Approval** (`nominations`) - staff proposals for
  who gets invited, bundled when multiple people nominate the same person,
  decided individually or in a batch round.
- **Module 3: Status Event Log** (`invitations`) - an append-only
  invited/accepted/declined/promoted/no-show log, overbooking-aware
  capacity math, waitlist promotion suggestions, bilingual (EN/DE) email
  reply classification, and bulk Excel import that reuses Golden Record
  dedup instead of exact-email matching.
- `events` - the shared `Event` model (capacity, category, historical
  show rate) both of the above build on.

Not yet built: the seating engine (Module 4) and the live-schedule /
EventMobi replacement (Module 5).

## Stack

Django + Django REST Framework, Postgres. The seating engine (Module 4)
will run as a separate Python worker; a React/Vite frontend is not part of
this slice yet - the Django admin is the only UI right now.

## Local setup

```bash
docker compose up -d db          # Postgres on localhost:5432

cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env             # adjust if your local Postgres differs
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Admin UI: http://localhost:8000/admin/
API root: http://localhost:8000/api/

## Module 1 - Golden Record: how duplicate review works

- Every new `Person` (API, admin, or a future import/email-parsing path)
  is fuzzy-matched against existing active people (name similarity +
  shared non-generic email domain + organization overlap). Matches above
  `GOLDEN_RECORD_DUPLICATE_THRESHOLD` (default 75) become a pending
  `DuplicateCandidate` - nothing is ever merged automatically.
- Review pending candidates and confirm/reject them in
  **Admin > People > Duplicates** (bulk actions support batch cleanup of
  legacy data) or via `POST /api/duplicate-candidates/{id}/confirm/` and
  `/reject/`.
- `python manage.py scan_duplicates` pairwise-scans all existing people
  once - the batch-cleanup mode for legacy data that never went through
  fuzzy matching on creation.
- `python manage.py flag_stale_persons` marks people whose
  `last_verified_at` is older than `GOLDEN_RECORD_STALE_MONTHS` (default
  18) as `flagged_for_review`; see `GET /api/people/needs-review/`.
- Every merge is logged in **Admin > People > Merge log** with enough
  detail (which emails moved) to revert it, or via
  `POST /api/merge-logs/{id}/revert/`.

## Module 2 - Nomination & Approval

- `POST /api/nominations/` with either an existing `nominee` (a Person) or
  a free-text `nominee_name`/`nominee_organization` for a brand-new contact.
- `GET /api/nominations/grouped-pending/?event=<id>` bundles duplicate
  proposals for the same nominee into one group for a single decision.
- `POST /api/nominations/{id}/approve/`, `/reject/`, `/waitlist/` decide a
  nomination and every other open nomination for the same nominee at once.
  Approving a brand-new contact creates their Person record, which runs
  through Module 1's normal dedup check.
- `POST /api/nominations/batch-decide/` applies a whole slate of decisions
  in one call - the "batch round before a deadline" mode.
- Approval fires a `nomination_approved` signal; `invitations` listens for
  it and creates the nominee's first `InvitationEvent` automatically.

## Module 3 - Status Event Log

- `InvitationEvent` is an append-only log (`invited` / `accepted` /
  `declined` / `promoted_from_waitlist` / `no_show`) - current status for a
  person/event is always the latest row, never an editable field.
- `GET /api/capacity/?event=<id>` returns accepted count, expected
  attendance (accepted × `historical_show_rate`), and the resulting seat
  buffer - the overbooking math behind "do we actually need to promote
  someone."
- `GET /api/promotion-suggestions/?event=<id>` shows the next waitlisted
  nominations in priority order; nothing is sent automatically.
  `POST /api/invitation-events/promote-from-waitlist/` is the explicit
  human confirmation that turns a suggestion into a real invitation.
- `POST /api/invitation-events/bulk-import/` is the Excel/CSV upload path:
  an existing email reuses the existing Person, a new email creates a new
  Person (triggering Module 1's fuzzy dedup) instead of just checking for
  an exact email match like the system it replaces.
- Email replies: `invitations.services.email_parsing` classifies inbound
  text (English and German keywords) and matches it to an invitation via
  `conversation_id` (preferred) or `tracking_code`. Ambiguous replies, or
  ones that don't match a known invitation, are logged as `EmailReply`
  rows needing manual resolution - `POST /api/email-replies/{id}/resolve/`
  - and nothing is auto-replied to. This module does the classification
  and matching a Microsoft Graph webhook handler would call after
  fetching a message's body; it does not talk to Graph itself (no Azure
  tenant credentials exist in this environment).
- `StandbyContact` (**Admin > Invitations > Standby contacts**) is the
  visible day-of-event escalation list for last-minute cancellations -
  intentionally not automated, just made visible.

## Tests

```bash
cd backend
python manage.py test
```
