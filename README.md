# EventFlow

Invitation/guest management and seating for large recurring conferences.
This repo currently implements **Module 1: Golden Record** - a stable
person identity (`person_id`) with fuzzy duplicate detection that every
later module (nominations, invitations, seating) will reference. Later
modules (nomination/approval, invitation status log, seating engine,
live schedule) build on top of this and are not part of this slice yet.

## Stack

Django + Django REST Framework, Postgres. Later modules add a separate
Python worker (seating optimization) and a React/Vite frontend - not part
of this initial slice.

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

## Golden Record: how duplicate review works

- Every new `Person` (API, admin, or a future import/email-parsing path)
  is fuzzy-matched against existing active people (name similarity +
  shared non-generic email domain + organization overlap). Matches above
  `GOLDEN_RECORD_DUPLICATE_THRESHOLD` (default 75) become a pending
  `DuplicateCandidate` - nothing is ever merged automatically.
- Review pending candidates and confirm/reject them in
  **Admin > Duplicate candidates** (bulk actions support batch cleanup of
  legacy data) or via `POST /api/duplicate-candidates/{id}/confirm/` and
  `/reject/`.
- `python manage.py scan_duplicates` pairwise-scans all existing people
  once - the batch-cleanup mode for legacy data that never went through
  fuzzy matching on creation.
- `python manage.py flag_stale_persons` marks people whose
  `last_verified_at` is older than `GOLDEN_RECORD_STALE_MONTHS` (default
  18) as `flagged_for_review`; see `GET /api/people/needs-review/`.
- Every merge is logged in `PersonMergeLog` with enough detail (which
  emails moved) to revert it: **Admin > Person merge logs** action, or
  `POST /api/merge-logs/{id}/revert/`.

## Tests

```bash
cd backend
python manage.py test people
```
