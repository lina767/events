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
- **Module 4: Seating Engine** (`seating`) - simulated annealing with a
  warm start over tables, hard-constraint/relationship scoring,
  human-confirmable proposals, and local reoptimization scoped to the
  table(s) a change actually touched.
- **Module 5: Live Schedule** (`schedule`) - the EventMobi replacement:
  an honest traffic-light schedule, a no-login per-room update page,
  personal agenda, networking search over the Golden Record, and polling
  based announcements.
- `events` - the shared `Event` model (capacity, category, historical
  show rate) every module above builds on.

All five modules from the original spec are now implemented.

## Stack

Django + Django REST Framework, Postgres. The seating engine (Module 4)
runs synchronously in-process here; the spec's separate-Python-worker
design (triggered by a job queue) is the natural next step once seating
runs at real conference scale, but isn't wired up in this repo. A
React/Vite frontend is not part of this slice yet - the Django admin and
the raw API are the only UI right now.

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

## Module 4 - Seating Engine

- `POST /api/seating/assignments/optimize/` (`event`, `iterations`,
  `seed`) runs a full simulated-annealing pass over every `Table` for the
  event's accepted attendees, warm-started from any existing
  `TableAssignment` rows - never from an empty room.
- Score per table: `w1*sector_diversity + w2*seniority_balance +
  w3*relationship_bonus - LARGE_PENALTY*hard_exclusion_violations`,
  weights configurable per event via `SeatingWeights` (equal by default).
  `RelationshipEdge` pairs are either a soft "should sit together" bonus
  or, when `is_hard_constraint=True`, a hard "must sit together"
  (positive) or "must not" (negative) rule.
- `SeatPin` fixes a specific person's table for an event, overriding the
  optimizer for them - set/cleared via
  `POST /api/seating/assignments/pin/` and `/unpin/`.
- `POST /api/seating/assignments/reoptimize-local/`
  (`changed_person_ids`) is the response to a decline/promotion: it only
  touches the table(s) that lost/gained a guest plus up to two
  lowest-capacity neighbors, not a global re-run over every table.
- Every assignment starts with `is_confirmed=False` and a plain-language
  `rationale` (e.g. "high sector diversity, moderate seniority mix").
  Nothing is communicated to guests until
  `POST /api/seating/assignments/confirm/` - and a later reoptimization
  reopens confirmation for whatever it touched.

## Module 5 - Live Schedule

- `Session.status` (`confirmed`/`delayed`/`running`/`cancelled`) plus
  `last_confirmed_at` drive an honest traffic light
  (`schedule.services.traffic_light`): green only while recently
  confirmed, yellow when delayed, and gray once confirmation goes stale
  (`SCHEDULE_STALE_MINUTES`, default 20) - a stale time is never shown as
  if it were still certain.
- Each `Room` has an unguessable `update_token` instead of a login:
  `GET /api/schedule/rooms/<token>/status/` shows just the current and
  next session, and `POST .../update/` applies one of the one-tap actions
  (`confirm`, `delay_10`, `delay_30`, `running`, `cancelled`) - the
  response includes subsequent sessions in the room as shift candidates,
  confirmed via `POST .../apply-shift/`, never forced automatically.
- Personal agenda (`PersonalAgendaItem`) just bookmarks a `Session` row,
  so a delay reorders a participant's agenda without any separate sync.
- Networking reuses the Golden Record directly - `GET
  /api/schedule/attendees/?event=&q=&sector=` searches accepted attendees'
  name/organization/sector tags, no separate profile model.
- `GET /api/schedule/announcements/feed/?event=&sector=` is the polling
  endpoint participants hit every 15-30s for both schedule and
  announcements; a targeted announcement (`audience_sector_tag`) only
  reaches its own track, never everyone.

## Tests

```bash
cd backend
python manage.py test
```
