# Winzapp

Winzapp is a WhatsApp-first diagnostics clinic operations suite. Patients use WhatsApp for consent and diagnostics interactions; clinic owners use a small web dashboard for bookings, reports, failed-message recovery, catalog maintenance, and settings.

**Pilot status:** the three implementation sprints are recorded complete in the project task board. The next gates are the pilot release checklist, deployed smoke tests, and pilot feedback capture.

Winzapp handles operational workflows only. It is not clinical decision support, an EMR, a prescription system, or a patient portal.

## Pilot Scope

Implemented surfaces:

| Surface | Purpose |
| --- | --- |
| WhatsApp webhook | Signature verification, idempotency, inbound logging, failure capture, and patient responses |
| Diagnostics flows | Consent, walk-in booking, home collection, report inquiry, and cancellation modules |
| Owner API | OTP authentication, clinic settings, test bookings, report upload, patients, catalog, and failed-message retry |
| Dashboard | Operations-focused React interface for the owner API |
| Automation services | Fasting reminders, recalls, review requests, daily digest, heartbeat, and alerts |
| Operations | PostgreSQL/Redis health checks, structured logs, optional Sentry/Logfire, Railway deployment configuration |

The pilot intentionally excludes GP appointment chat flows, online payments, broadcasts, automated onboarding, password-protected PDFs, and multi-replica scheduling. See [docs/product/mvp-scope.md](docs/product/mvp-scope.md) for the full boundary.

## Prerequisites

| Tool | Version or requirement | Used for |
| --- | --- | --- |
| Python | 3.11+ | FastAPI backend, migrations, tests |
| Docker Desktop | Linux engine running with Compose | Local PostgreSQL and Redis |
| Node.js | 20.19+ or 22.12+ | Vite 7 dashboard |
| npm | Bundled with Node.js | Dashboard dependencies and scripts |
| Meta, Supabase, Groq credentials | Only needed for real external interactions | WhatsApp delivery, PDF storage, LLM fallback |

Local Docker exposes PostgreSQL on `localhost:55432` and Redis on `localhost:6379`. PostgreSQL data is kept in the named `postgres_data` volume; Redis remains ephemeral because application state can be rebuilt from PostgreSQL.

## Quickstart

Run these commands from the repository root in PowerShell.

1. Start the local dependencies and create the backend environment.

   ```powershell
   docker compose up -d postgres redis
   docker compose ps
   Copy-Item .env.example .env
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install --upgrade pip
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

2. Prepare local data and start the API.

   ```powershell
   .\.venv\Scripts\python.exe -m alembic upgrade head
   .\.venv\Scripts\python.exe scripts\seed_pilot.py
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
   ```

3. Check that PostgreSQL and Redis are available through the API.

   ```powershell
   Invoke-RestMethod http://127.0.0.1:8000/health
   ```

   Expected healthy response:

   ```json
   {
     "status": "ok",
     "checks": {
       "database": "ok",
       "redis": "ok"
     }
   }
   ```

4. Start the dashboard in a second PowerShell session.

   ```powershell
   Set-Location frontend
   npm ci
   npm run dev
   ```

Open the dashboard at `http://127.0.0.1:5173`. The Vite development server proxies `/api` requests to the API at `http://127.0.0.1:8000`.

FastAPI exposes interactive API documentation at `http://127.0.0.1:8000/docs`.

## Configuration

Copy `.env.example` to `.env` for development. Do not commit credentials.

| Variable | Default in `.env.example` | Needed for |
| --- | --- | --- |
| `APP_ENV` | `development` | Runtime environment and logging behavior |
| `APP_NAME` | `WhatsApp Clinic Suite` | FastAPI application title |
| `API_V1_PREFIX` | `/api/v1` | Declared API prefix; routers currently mount `/api/v1` explicitly |
| `DATABASE_URL` | Local PostgreSQL on `55432` | API data store and migrations |
| `TEST_DATABASE_URL` | Local PostgreSQL on `55432` | Backend test suite |
| `REDIS_URL` | `redis://localhost:6379/0` | Cache, OTP state, and scheduler heartbeat |
| `WA_APP_SECRET` | Empty | Webhook signature verification |
| `WA_VERIFY_TOKEN` | Empty | Meta webhook registration |
| `WA_ACCESS_TOKEN` | Empty | Outbound WhatsApp messages and OTP delivery |
| `LLM_PROVIDER` | `groq` | Optional LLM fallback provider |
| `LLM_MODEL` | `llama-3.3-70b-versatile` | Optional LLM fallback model |
| `GROQ_API_KEY` | Empty | Optional Groq-backed fallback |
| `LLM_TIMEOUT_SECONDS` | `10` | LLM request timeout |
| `SUPABASE_URL` | Empty | Report PDF storage and signed URLs |
| `SUPABASE_SERVICE_KEY` | Empty | Report PDF storage and signed URLs |
| `SUPABASE_STORAGE_BUCKET` | `reports` | Storage bucket for reports |
| `JWT_SECRET` | Local placeholder | Owner JWT signing; replace outside local development |
| `JWT_ACCESS_TOKEN_MINUTES` | `30` | Owner session lifetime |
| `SENTRY_DSN` | Empty | Optional Sentry reporting |
| `LOGFIRE_TOKEN` | Empty | Optional Logfire reporting |
| `OBSERVABILITY_ALERTS_ENABLED` | `true` | Operational alert emission |
| `WEBHOOK_LATENCY_ALERT_MS` | `15000` | Slow webhook threshold |
| `SCHEDULER_HEARTBEAT_MAX_AGE_SECONDS` | `300` | Missing/stale heartbeat threshold |

Automated tests mock calls to Meta, Groq, and Supabase. Real credentials are needed only when exercising those integrations against external services.

## Interfaces

### HTTP Routes

| Route group | Path | Notes |
| --- | --- | --- |
| Health | `GET /health` | Reports database and Redis readiness |
| WhatsApp webhook | `GET/POST /webhooks/whatsapp` | Meta verification and inbound delivery |
| Authentication | `POST /api/v1/auth/otp/send`, `POST /api/v1/auth/otp/verify` | Owner OTP login |
| Clinic settings | `/api/v1/clinics/{clinic_id}` | Owner-authenticated settings reads and updates |
| Test bookings | `/api/v1/clinics/{clinic_id}/test-bookings` | List, create, update, and soft-delete bookings |
| Report upload | `/api/v1/clinics/{clinic_id}/test-bookings/{booking_id}/report-upload` | Dashboard PDF delivery path |
| Patients and catalog | `/api/v1/clinics/{clinic_id}/patients`, `/api/v1/clinics/{clinic_id}/tests` | Dashboard maintenance |
| Failed messages | `/api/v1/clinics/{clinic_id}/failed-messages` | Dead-letter list and retry |

Protected clinic operations use the bearer access token returned by OTP verification. All tenant operations are scoped by `clinic_id`.

### Request Flow

```text
Patient -> Meta Cloud API -> /webhooks/whatsapp -> flow services -> PostgreSQL
                                      |                 |
                                      |                 +-> Redis cache/session state
                                      +--------------------> Meta Cloud API response

Owner -> React dashboard -> /api/v1 -> PostgreSQL / Supabase Storage / WhatsApp
```

Incoming WhatsApp messages must preserve this processing order: verify signature, check idempotency, write the inbound message, run the flow, and capture failures in `failed_messages`. Read [docs/architecture/webhook-pipeline.md](docs/architecture/webhook-pipeline.md) and [INVARIANTS.md](INVARIANTS.md) before changing webhook, patient, booking, or tenant-scoped code.

## Pilot Readiness Notes

The release checklist is still outstanding. Two runtime wiring points must be verified or resolved before relying on end-to-end pilot automation:

- `app/webhooks/whatsapp.py` currently invokes `ConsentFlow` directly; confirm routing into the implemented diagnostics booking, collection, inquiry, and cancellation flows.
- `app/services/scheduler.py` defines the APScheduler jobs, but `app/main.py` does not start a scheduler instance; starting the API alone does not establish `scheduler:heartbeat`.

These are deployment blockers for a fully automated pilot, not prerequisites for exploring the dashboard or running the existing automated tests.

## Development And Verification

Run the backend local-CI path:

```powershell
.\scripts\local_ci.ps1
```

Or run individual backend checks after dependencies and migrations are available:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m mypy app
.\.venv\Scripts\python.exe -m ruff check app tests
```

Run dashboard checks:

```powershell
Set-Location frontend
npm test
npm run build
```

For a real webhook round trip, configure the WhatsApp variables, expose port `8000` with a public HTTPS tunnel, and register `/webhooks/whatsapp` with Meta. Template-driven messages cannot be used in the pilot until their templates are approved in Meta.

## Deployment

The pilot deployment target is Railway:

- The backend `Dockerfile` uses a multi-stage build, installs only `requirements-prod.txt`, and runs Uvicorn as an unprivileged runtime user.
- One backend web replica only, because APScheduler is designed to run in-process for the MVP.
- Migrations execute through Railway's `preDeployCommand`.
- Railway checks `/health` before treating a deployment as ready.
- Production credentials are supplied as Railway environment variables, never from a committed `.env`.

Before pilot traffic, execute [docs/ci-cd/release-checklist.md](docs/ci-cd/release-checklist.md), including webhook idempotency, report delivery, dead-letter retry, tenant isolation, alerts, and rollback readiness.

## Documentation Map

| Topic | Document |
| --- | --- |
| Local development | [docs/runbooks/local-dev.md](docs/runbooks/local-dev.md) |
| Pilot scope | [docs/product/mvp-scope.md](docs/product/mvp-scope.md) |
| Architecture decisions | [docs/architecture/decisions.md](docs/architecture/decisions.md) |
| Data model | [docs/architecture/data-model.md](docs/architecture/data-model.md) |
| Webhook pipeline | [docs/architecture/webhook-pipeline.md](docs/architecture/webhook-pipeline.md) |
| Railway deployment | [docs/ci-cd/railway.md](docs/ci-cd/railway.md) |
| Release checklist | [docs/ci-cd/release-checklist.md](docs/ci-cd/release-checklist.md) |
| Incident response | [docs/runbooks/incident-response.md](docs/runbooks/incident-response.md) |
| Active task board | [docs/project/tasks.md](docs/project/tasks.md) |

## Contributing

Read [AGENTS.md](AGENTS.md) and [INVARIANTS.md](INVARIANTS.md) before editing the codebase. Keep changes scoped, include tests for behavior changes, and run the relevant verification commands before committing.

## License

See [LICENSE](LICENSE).
