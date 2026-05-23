# Winzapp

Winzapp is a WhatsApp-first clinic automation suite. It gives patients a WhatsApp-only experience for consent, diagnostics test booking, home collection, report status, cancellation, report delivery, reminders, recalls, and review requests. Clinic owners and staff use a minimal web dashboard for operational work.

The current implementation is the diagnostics-clinic Pilot MVP. The codebase also includes foundational appointment, doctor, slot, review, and broadcast models for the broader clinic SaaS direction after the pilot.

## What It Does

Patient workflows:

- First-message consent before automation.
- Rule-first diagnostics intent routing with optional Groq-backed LLM fallback.
- Walk-in test booking.
- Home collection booking with address and slot capture.
- Report inquiry.
- Booking cancellation.
- Report PDF delivery through WhatsApp documents.
- Recall and reminder messages.

Clinic owner workflows:

- OTP login with short-lived JWT access tokens.
- Overview dashboard for operations.
- Test booking list and status updates.
- Pending report upload and delivery.
- Failed inbound message inbox and retry.
- Patient and test catalog management.
- Clinic settings management.
- Admin WhatsApp commands for daily diagnostics operations.

Automation and operations:

- Fasting reminders.
- Review requests.
- Recall reminders.
- Daily owner digest.
- Scheduler heartbeat.
- Structured logs, request context, optional Sentry/Logfire, and operational alerts.

## Architecture

```text
Backend:      Python 3.11+, FastAPI async
Database:     PostgreSQL, SQLAlchemy 2.0 async, Alembic
Cache:        Redis
Scheduler:    APScheduler AsyncIOScheduler
WhatsApp:     Meta Cloud API direct
LLM:          Provider abstraction, Groq default
Storage:      Supabase Storage
Auth:         OTP login + short-lived JWT
Frontend:     React, Vite, Tailwind
Deployment:   Railway pilot, Hetzner + Docker Compose later
```

Every tenant-scoped table uses `clinic_id`. Any query touching patient, booking, session, message, or appointment data must filter by `clinic_id`.

## Repository Layout

```text
app/                    FastAPI app, models, schemas, services, flows, API routes
frontend/               React dashboard
migrations/             Alembic migrations
scripts/                Seed and Meta template helper scripts
tests/                  Backend tests
docs/                   Architecture, product, CI/CD, runbooks, and task board
AGENTS.md               Active project state and coding guardrails
INVARIANTS.md           Non-negotiable engineering invariants
docker-compose.yml      Local PostgreSQL and Redis
```

## Local Setup

Start local services:

```powershell
docker compose up -d postgres redis
```

Create the backend environment:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Copy and fill environment variables:

```powershell
Copy-Item .env.example .env
```

Apply migrations and seed the pilot clinic:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe scripts\seed_pilot.py
```

Run the API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Install and run the dashboard:

```powershell
cd frontend
npm install
npm run dev
```

Dashboard URL: `http://127.0.0.1:5173`

API health check: `http://127.0.0.1:8000/health`

## Verification

Backend:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m mypy app
.\.venv\Scripts\python.exe -m ruff check app
```

Frontend:

```powershell
cd frontend
npm test
npm run build
```

The local CI helper is documented in [docs/ci-cd/local-ci.md](docs/ci-cd/local-ci.md). Pilot launch checks are in [docs/ci-cd/release-checklist.md](docs/ci-cd/release-checklist.md).

## Environment Variables

Use `.env.example` as the source of truth. Required groups:

- Database and Redis: `DATABASE_URL`, `TEST_DATABASE_URL`, `REDIS_URL`
- WhatsApp: `WA_APP_SECRET`, `WA_VERIFY_TOKEN`, `WA_ACCESS_TOKEN`
- LLM: `LLM_PROVIDER`, `LLM_MODEL`, `GROQ_API_KEY`
- Supabase Storage: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_STORAGE_BUCKET`
- Auth: `JWT_SECRET`, `JWT_ACCESS_TOKEN_MINUTES`
- Observability: `SENTRY_DSN`, `LOGFIRE_TOKEN`, alert thresholds

## Pilot Scope

Included:

- Diagnostics WhatsApp workflows.
- Manual/offline payment handling.
- Report PDF upload and WhatsApp delivery.
- Reminder, recall, review-request, and daily-digest automation.
- Minimal owner/staff dashboard.

Excluded from the pilot:

- GP appointment booking flows.
- Razorpay subscriptions.
- Password-protected PDFs.
- Broadcast campaigns.
- Automated clinic onboarding and Meta Embedded Signup.
- Multi-replica production scaling.

See [docs/product/mvp-scope.md](docs/product/mvp-scope.md) for the full scope boundary.
