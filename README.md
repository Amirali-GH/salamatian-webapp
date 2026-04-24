# Salamatian — Used Cars Management Platform

Production-ready monolithic FastAPI application that serves both REST APIs
and server-rendered HTML for a used-car dealership. A single FastAPI process
handles public pages, the admin panel, the JSON API, static assets, and
uploaded media.

Features:

- **Car inventory** with draft → pending → published → archived lifecycle.
- **Excel synchronization robot** — upload an `.xlsx`, preview the diff (new /
  updated / removed / warnings), apply with a single click. Never hard-deletes.
  Daily Celery Beat task scans an inbox directory and notifies admins.
- **Lead management** — consultation and sell-request intake with image upload,
  IP-based rate limiting.
- **Admin panel** — dashboard, cars list/edit, Excel import/preview, leads,
  media browser, logs (audit + price history), user management.
- **Role-based access** — `admin` / `operator` / `viewer`.
- **Audit logging** covering create / update / delete / archive / publish and
  dedicated `price_change` entries.
- **Redis cache** for `/api/cars` responses with automatic invalidation.
- **Pluggable notifications**: admin-panel bell, optional Telegram, optional SMTP.

## Stack

| Layer     | Technology                                                    |
| --------- | ------------------------------------------------------------- |
| Framework | FastAPI (Python 3.11+), Uvicorn                               |
| ORM       | SQLAlchemy 2.x async                                          |
| DB        | PostgreSQL 15 (SQLite used for tests)                         |
| Migration | Alembic                                                       |
| Template  | Jinja2 server-side rendering + HTMX + Alpine.js               |
| Validator | Pydantic v2                                                   |
| Auth      | JWT (access + refresh), HttpOnly cookie + `Authorization` hdr |
| Queue     | Celery + Redis, Celery Beat (daily 08:00)                     |
| Cache     | Redis                                                         |
| Storage   | Local FS with an S3-compatible interface (swap later)         |
| Testing   | pytest + httpx + aiosqlite                                    |

## Quick start (Docker)

```bash
cp .env.example .env        # then edit SECRET_KEY, bootstrap admin, etc.
make dev                    # builds images and starts web + worker + beat + pg + redis
make migrate                # applies Alembic migrations
make seed                   # creates the bootstrap admin user (idempotent)
```

Endpoints after `make dev`:

- Public site:  <http://localhost:8000/>
- Admin panel: <http://localhost:8000/admin/>
- OpenAPI:     <http://localhost:8000/docs>
- Health:      <http://localhost:8000/healthz>

Default admin credentials come from `.env`:

```
BOOTSTRAP_ADMIN_USERNAME=admin
BOOTSTRAP_ADMIN_PASSWORD=ChangeMe!123
```

Change them before any deployment.

## Project layout

```
app/
├── main.py              FastAPI app factory + routers + static/media mounts
├── config.py            Pydantic Settings (env-based)
├── database.py          Async engine, session, Base
├── models/              SQLAlchemy models (cars, images, leads, audit, …)
├── schemas/             Pydantic v2 request/response schemas
├── api/                 JSON API routers (under /api/*)
├── admin/               HTML admin routers (under /admin/*)
├── public/              Public HTML routes (/, /car/{id})
├── services/            Business logic (excel_sync, car_service, media, …)
├── core/                security.py (JWT), permissions.py, cache.py
├── workers/             Celery app + tasks + beat schedule
├── templates/           Jinja2 templates (admin + public)
├── static/              CSS / JS
└── scripts/             seed_admin.py
alembic/                 Database migrations
storage/uploads/         cars/ leads/ excel/ (+ excel/inbox/)
tests/                   pytest suite
```

## API overview

All endpoints are documented at `/docs` and grouped by tag:

- `public`   — car listing & detail, consultation / sell leads.
- `auth`     — `POST /api/auth/login`, `/refresh`, `/logout`, `GET /me`.
- `admin`    — car CRUD, image upload/reorder, lead management, Excel upload /
  apply, notifications, logs.

Public list endpoint (`GET /api/cars`) supports: `brand`, `model`, `year_min`,
`year_max`, `price_min`, `price_max`, `gearbox`, `fuel_type`, `location`,
`search`, `limit`, `offset`, `sort`. Responses are cached in Redis for 60s and
invalidated on any admin mutation.

## Excel sync

1. Operator uploads `cars.xlsx` to `POST /api/admin/excel/upload` (or via
   `/admin/excel` in the panel). File saved to
   `storage/uploads/excel/{timestamp}_{name}`.
2. The service parses synchronously and returns a **diff object + token**.
   Nothing is written to the database.
3. Operator reviews the diff at `/admin/excel/preview/{token}` and clicks
   **Apply changes**.
4. `POST /api/admin/excel/apply` (or the panel's Apply button) runs the apply
   stage inside a single transaction:
   - new rows → `status=pending`, `source=excel` + `create` audit entry
   - updates  → field-level diff + `price_change` audit entry when price changes
   - missing  → `status=archived` (never deleted) + `archive` audit entry +
     admin notification
5. `excel_import_logs` receives a summary row with the warnings list.

Matching key: `excel_row_id` if present, else `(brand + model + year)`
(case-insensitive).

Beat task `scan_excel_inbox` runs daily at 08:00 Tehran time, parses every
`.xlsx` in `storage/uploads/excel/inbox/` in **preview mode only**, and
notifies admins with the preview URL — humans still approve.

## Rate limiting

`POST /api/leads/consultation` and `POST /api/leads/sell` are limited to
`PUBLIC_LEAD_RATE_PER_HOUR=10` per IP via Redis. Tune via `.env`.

## Caching & invalidation

- List responses: key = `cars:list:<hash>`, TTL 60s.
- Detail responses: key = `cars:detail:<id>`, TTL 300s.

Any create/update/delete/publish/archive call — including Excel apply — calls
`invalidate_cars_cache()` which drops every `cars:*` key.

## Notifications

- **Admin panel** (always): rows in `notifications`, exposed at
  `GET /api/admin/notifications/unread`.
- **Telegram**: set `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`.
- **Email (SMTP)**: set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`,
  `SMTP_FROM`.

All notifications are dispatched from Celery tasks so HTTP handlers stay fast.

## Testing

```bash
make test        # runs inside the web container
```

or locally:

```bash
pip install .[dev]
pytest -q --cov=app --cov-report=term-missing
```

The Excel-sync module is covered at ≥ 90% (see `tests/test_excel_sync.py`).
Tests use aiosqlite in-memory and a fake Redis, so no external services are
needed.

## Security notes

- Passwords hashed with bcrypt via passlib.
- JWT signed with HS256 — rotate `SECRET_KEY` before production.
- `access_token` stored as HttpOnly, SameSite=Lax cookie (`Secure` in
  production).
- All money stored as `Numeric(18, 2)`; never `float`.
- Only SQLAlchemy parameterized queries — no raw-SQL injection surface.
- Excel files are **not** served through the public `/media` mount; downloads
  require an authenticated `GET /api/admin/excel/download/{id}`.
- Global exception handler returns a consistent JSON error envelope for API
  routes and a user-friendly template for admin routes, carrying a request ID.

## Deployment

Services in `docker-compose.yml`: `web` (FastAPI), `worker` (Celery),
`beat` (Celery Beat), `postgres`, `redis`. Mount a reverse proxy (nginx, Caddy)
in front of `web` for TLS termination in production.

## License

Proprietary — see `LICENSE`.
