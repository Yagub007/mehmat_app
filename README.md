# Mehmat — NMT Mathematics Telegram Mini App (Backend)

Production-ready Django REST Framework backend powering a Telegram Mini App that
helps students prepare for the Ukrainian **NMT Mathematics** exam.

## Features

- **Telegram Mini App authentication** — server-side verification of `initData`
  (HMAC-SHA256), automatic user provisioning, and JWT access/refresh tokens.
- **Study materials** — categorised PDFs with thumbnails, search and filtering.
- **Testing system** — single/multiple/ordering questions, server-authoritative
  timers, one official attempt per user, and fully server-side scoring.
- **Gamification** — points, rank tiers, daily streaks, achievements and a
  paginated leaderboard.
- **Notifications** — in-app notifications with read state and unread counts.
- **Professional Django admin**, **OpenAPI docs** (Swagger/Redoc), throttling,
  optimised queries, and a comprehensive test suite.

## Tech stack

Python 3.13 · Django 5.2 · Django REST Framework · PostgreSQL · SimpleJWT ·
drf-spectacular · django-filter · django-cors-headers · WhiteNoise · Pillow.

## Project layout

```
mehmat_project/
├── config/                 # Django project (settings, urls, wsgi/asgi)
├── mehmat_app/
│   ├── models/             # User, Material, Test/Question/Choice, Submission…
│   ├── serializers/        # DRF serializers (thin, per-domain)
│   ├── views/              # Thin views / viewsets
│   ├── services/           # Business logic (telegram, scoring, sessions, …)
│   ├── selectors/          # Optimised read queries (leaderboard, statistics)
│   ├── migrations/         # Schema + achievement seed data
│   ├── tests/              # Unit & integration tests
│   ├── admin.py  permissions.py  validators.py  throttles.py  pagination.py
│   ├── constants.py  managers.py  signals.py  urls.py
├── manage.py  requirements.txt  .env.example
```

## Setup

```bash
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # then edit values (see below)
createdb mehmat               # or use an existing PostgreSQL database

python manage.py migrate
python manage.py createsuperuser --telegram_id <your_telegram_id>
python manage.py runserver
```

### Environment variables

All configuration comes from the environment (`.env` in development). See
[`.env.example`](.env.example). Key variables:

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Django secret key |
| `DEBUG` | `True`/`False` |
| `ALLOWED_HOSTS` | Comma-separated hosts |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT` | PostgreSQL |
| `JWT_SECRET` | JWT signing key (falls back to `SECRET_KEY`) |
| `TELEGRAM_BOT_TOKEN` | Bot token used to verify `initData` |
| `TELEGRAM_AUTH_MAX_AGE_SECONDS` | Max age of `initData` (default 24h) |
| `MEDIA_ROOT` / `MEDIA_URL` | Uploaded files (PDFs, thumbnails) |
| `CORS_ALLOWED_ORIGINS` | Allowed Mini App origins |

## API (base path `/api/v1/`)

| Method | Path | Description |
| --- | --- | --- |
| POST | `auth/telegram/` | Authenticate via Telegram `initData`, returns JWT pair |
| POST | `auth/token/refresh/` | Refresh access token |
| GET/PATCH | `profile/` | Current user's profile |
| GET | `profile/statistics/` | Aggregate statistics |
| GET | `profile/achievements/` | Achievements with unlock status |
| GET | `categories/` | Category tree (imported from Drive folders) |
| GET | `materials/` · `materials/{id}/` | List/retrieve materials (search, filter) |
| GET | `tests/` · `tests/{id}/` | List/retrieve tests (answers hidden) |
| POST | `tests/{id}/start/` | Start a server-timed session |
| POST | `tests/{id}/submit/` | Submit answers for grading |
| GET | `submissions/` · `submissions/{id}/` | Own submissions |
| GET | `leaderboard/` · `leaderboard/me/` | Ranking + own position |
| GET | `achievements/` | Achievement catalogue |
| GET | `notifications/` | List notifications |
| POST | `notifications/{id}/read/` | Mark one read |
| POST | `notifications/mark-all-read/` | Mark all read |
| GET | `notifications/unread-count/` | Unread count |
| GET | `schema/`, `schema/swagger/`, `schema/redoc/` | OpenAPI docs |

Authenticate requests with `Authorization: Bearer <access_token>`.

## Importing study materials (one-time, from a public Drive folder)

Study materials are imported from a **public** Google Drive folder — no API key,
credentials or service account required. The folder is downloaded with `gdown`,
its folder tree is recreated as a `Category` hierarchy, and every file is copied
into `MEDIA_ROOT` with only its relative path stored in the database. Materials
are then served locally, so any file type (PDF, video, presentation, doc, …)
opens directly from the app.

```bash
# Download a public folder and import everything
python manage.py import_materials --url "https://drive.google.com/drive/folders/<id>"

# Import an already-downloaded folder (skips the download step)
python manage.py import_materials --source /path/to/folder --root-name "Матеріали НМТ"

# Preview without writing anything
python manage.py import_materials --source /path/to/folder --dry-run
```

The import is **idempotent** — folders/files are keyed by their path relative to
the import root, so re-running never duplicates and preserves existing IDs.
Downloads are **resilient**: the full file list is enumerated first, then each
file is fetched individually with retries/backoff and resume, so one file that
Google temporarily rate-limits never aborts the rest. Any files that still fail
are reported and picked up on the next run.

The `Тести` (tests) folder is **excluded by default** (`--exclude Тести`) — tests
are managed as structured JSON, not imported as documents (see below). Each
top-level folder becomes a filterable subject on the website, and selecting it
shows every material nested beneath it (subtree filtering).

## Importing tests (JSON)

Tests are authored as JSON and loaded into the Test / Question / Choice models:

```bash
python manage.py import_tests path/to/tests.json      # one file
python manage.py import_tests path/to/tests_dir/      # every *.json in a dir
python manage.py import_tests tests.json --dry-run    # validate only
```

See [`sample_tests.json`](sample_tests.json) for the format (single/multiple/
ordering questions supported). The importer validates each test, is idempotent
(tests are keyed by title — re-importing updates in place and replaces the
question set), and reports per-test errors without aborting the batch.

## Scoring & fairness rules (enforced server-side)

- Only the **first in-time attempt** counts as *official* and affects ranking.
- Timers are validated against a server-created `TestSession`; late submissions
  are graded for practice only.
- Scores and points are computed on the backend — the frontend never sends them.
- A partial unique constraint guarantees at most one official submission per
  (user, test); grading runs inside a transaction with row locking.

## Testing

```bash
python manage.py test mehmat_app
```

Covers Telegram auth, scoring, duplicate-submission prevention, timer
validation, leaderboard updates, permissions and input validation.

## Production notes

- Serve `MEDIA_ROOT` via a dedicated web server / object storage (Django only
  serves media when `DEBUG=True`). Static files are served via WhiteNoise.
- Set `DEBUG=False`; security headers (HSTS, secure cookies, SSL redirect) are
  enabled automatically.
- Run behind a WSGI/ASGI server (e.g. Gunicorn/Uvicorn) with `collectstatic`.
