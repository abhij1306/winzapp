# AGENTS.md — WhatsApp Clinic Suite
### External Brain | Read this at the start of every coding session

---

## ACTIVE SPRINT GOAL
**Sprint 3 of 3 — Automation, Dashboard, and Pilot Launch**
Build owner authentication, operational APIs, scheduler jobs, dashboard workflows, observability, and the pilot launch checklist. Keep the dashboard minimal and operations-focused for the diagnostics pilot.

Current focus: Sprint 3 dashboard setup: minimal dashboard → observability

---

## SYSTEM STATE

### ✅ Completed
- [x] S1-T01: Project scaffolding, config, and local services
- [x] S1-T02: Async database and Alembic setup
- [x] S1-T03: SQLAlchemy base mixins
- [x] S1-T04: SQLAlchemy models
- [x] S1-T05: Initial migration with RLS and triggers
- [x] S1-T06: Common and WhatsApp Pydantic schemas
- [x] S1-T07: Redis cache service
- [x] S1-T08: Utilities, structured logging, and audit service
- [x] S1-T09: Feature flags and LLM service abstraction
- [x] S1-T10: WhatsApp sender service
- [x] S1-T11: Flow engine base and consent flow
- [x] S1-T12: WhatsApp webhook handler
- [x] S1-T13: Local CI, GitHub Actions, and Railway skeleton
- [x] S1-T14: Pilot seed data and Meta template registration scaffold
- [x] S2-T01: Rule-first diagnostics intent router
- [x] S2-T02: Diagnostics test booking walk-in flow
- [x] S2-T03: Diagnostics home collection flow
- [x] S2-T04: Report inquiry and cancellation flows
- [x] S2-T05: Admin WhatsApp diagnostics commands
- [x] S2-T06: Storage service and report-ready API
- [x] S2-T07: Recall scheduling engine
- [x] S2-T08: Message template registration and reminder readiness
- [x] S3-T01: OTP auth API
- [x] S3-T02: Clinic settings API
- [x] S3-T03: Test booking operations API
- [x] S3-T04: Pending reports upload API
- [x] S3-T05: Patient and test catalog APIs
- [x] S3-T06: Failed message inbox and retry API
- [x] S3-T07: Scheduler jobs
- [x] S3-T08: Minimal dashboard frontend
- [x] S3-T09: Observability and alerting
- [x] S3-T10: Pilot launch checklist

### 🔄 In Progress
*(nothing currently in progress)*

### ⏭️ Immediate Next Steps (in order)
1. Run pilot release checklist
2. Complete deployed smoke tests
3. Start pilot feedback capture

---

## ARCHITECTURE SNAPSHOT

### Stack (do not deviate without updating this file)
```
Language:       Python 3.11+
Framework:      FastAPI (async)
ORM:            SQLAlchemy 2.0 (async) + Alembic migrations
Database:       PostgreSQL (Supabase for now, self-hosted later)
Cache:          Redis (aioredis) — Day 1, not optional
Task scheduler: APScheduler (AsyncIOScheduler)
WhatsApp:       Meta Cloud API direct (no BSP)
LLM:            Provider abstraction with Groq as default (intent + review replies)
Storage:        Supabase Storage (PDFs)
Auth:           JWT (short-lived access token + OTP login — no passwords)
Payments:       Manual/offline in Pilot MVP; Razorpay post-pilot
Frontend:       React + Vite + Tailwind (minimal dashboard - Sprint 3)
Deployment:     Railway.app (MVP) → Hetzner + Docker Compose (production)
```

### Multi-Tenancy Model
Every clinic is a tenant. The key is `clinic_id` on every table.
The rule: **if a query touches patient/appointment/booking data and does not filter by `clinic_id`, it is a bug.**
RLS is enabled in Postgres. The app layer also sets `app.clinic_id` per transaction.

### Conversation Architecture
Patient state lives in `conversation_sessions` table (Postgres) + Redis cache (30-min TTL).
Redis is the fast path. DB is the source of truth.
On cache miss → read DB → write back to Redis.
On session write → write-through (DB + Redis together, not one or the other).

### Webhook Architecture
Incoming message processing order (NEVER change this order):
1. Verify Meta signature
2. Idempotency check (`messages.wa_message_id`)
3. Log inbound message to DB (`messages` table) ← write-first, before any processing
4. Route to flow engine
5. On any exception → write to `failed_messages` table (never let it crash silently)

---

## FILE MAP (key files and what they own)

```
app/models/base.py              TimestampMixin, SoftDeleteMixin — applied to ALL mutable models
app/models/clinic.py            Clinic model + settings JSONB structure
app/models/conversation.py      ConversationSession model
app/models/failed_message.py    Dead-letter queue model
app/models/audit_log.py         Audit trail — 7-year retention (DPDP compliance)

app/schemas/common.py           PaginatedResponse + ErrorEnvelope — used on ALL endpoints
app/schemas/whatsapp_webhook.py Pydantic validation for all incoming WA payloads

app/services/cache.py           get_clinic_cached(), get_session_cached(), get_tests_cached()
                                invalidate_clinic_cache(), invalidate_tests_cache()
                                update_session_cache() — write-through pattern

app/services/feature_flags.py   require_feature(clinic_id, feature_name, db)
                                → raises HTTP 403 with error envelope if flag is off

app/services/audit.py           write_audit(db, clinic_id, action, entity_type, entity_id, diff)
                                → called after every state-changing operation
app/services/intent_router.py   Rule-first diagnostics intent router with feature-flagged LLM fallback

app/webhooks/whatsapp.py        Entry point for ALL incoming WhatsApp messages

app/flows/base_flow.py          Abstract base: handle(session, message, db) -> str
app/flows/consent_flow.py       MUST run on first-ever message from any patient

INVARIANTS.md                       Coding rules - read this too
docs/architecture/decisions.md      Why we made key architectural choices
docs/project/tasks.md               Atomic task list for current sprint
docs/product/traceability.md        Spec coverage map
```

---

## DISCOVERED GOTCHAS
*(Populated as we learn things — agent must add entries here when they find bugs/quirks)*

### WhatsApp Cloud API
- Meta **retries webhook delivery** if you don't respond with HTTP 200 within 20 seconds. This means the same `wa_message_id` will arrive 2–3 times if your server is slow. The idempotency check in step 2 of the webhook pipeline is not optional — it's the only thing preventing double-bookings.
- Message templates must be **approved by Meta before use**. During development, you can only send free-form messages within the 24-hour customer service window. Don't build scheduler flows that rely on templates until they're approved.
- The `from` field in the WA payload is a reserved Python keyword. Our Pydantic schema aliases it as `from_` — see `app/schemas/whatsapp_webhook.py`. Do not rename this.
- WhatsApp interactive list messages have a **10-item maximum per section** and a **3-button maximum** for button replies. If a test catalog has > 10 items, split into categories first.

### SQLAlchemy Async
- Use `AsyncSession` everywhere. Never mix sync and async sessions.
- `relationship()` calls need `lazy="selectin"` or explicit `await session.refresh(obj, ["relationship_name"])`. Do not use default lazy loading — it will raise `MissingGreenlet` errors in async context.
- `server_default=func.now()` is correct for `created_at`. `onupdate=func.now()` alone does NOT trigger on INSERT — you need both `server_default` and `onupdate` on `updated_at`.

### Redis / aioredis
- Use `aioredis.from_url()` not `Redis()` directly for async context.
- Always `await redis.setex(key, ttl, value)` — never `await redis.set(key, value)` without TTL for session data. Sessions must expire.
- JSON serialize everything stored in Redis. Python objects cannot be stored directly.

### PostgreSQL / Supabase
- Supabase RLS requires `SET app.clinic_id = '...'` **before** your query in the same transaction. Use a FastAPI middleware or dependency to set this at request start.
- Request handlers that commit more than once retain `app.clinic_id` for the database session and clear it before the pooled connection is returned; `SET LOCAL` alone is insufficient for these flows.
- `gen_random_uuid()` requires `pgcrypto` extension. Enable with: `CREATE EXTENSION IF NOT EXISTS pgcrypto;`
- Supabase Storage signed URLs expire. Default: 1 hour. For WhatsApp report delivery, set 24-hour expiry (`expires_in=86400`) — patients sometimes open the message hours later.

### Alembic
- When using `JSONB DEFAULT '{}'` in raw SQL, Alembic autogenerate will not detect JSONB changes. Review migration files manually after `--autogenerate`.
- Run `alembic upgrade head` in CI before tests — not just locally.

### APScheduler
- Set `timezone="Asia/Kolkata"` on the scheduler instance, not per-job. Otherwise cron jobs for 9 AM and 8 PM will fire at wrong times.
- APScheduler **does not survive process restarts** for in-progress jobs. For the MVP this is acceptable (jobs re-check DB state on next run). Document this limitation for operations.
- The scheduler heartbeat is written to Redis at `scheduler:heartbeat`; deleting or aging this key is the staging check for the missed-heartbeat alert.
- Scheduled patient and booking sends execute one clinic at a time with `app.clinic_id` set in the job transaction. Do not reintroduce cross-tenant scheduler queries.

### Multi-Tenancy
- If you ever write a utility function that queries patients or appointments without a `clinic_id` parameter, stop and refactor. There is no legitimate reason to query across tenants.
- The `UNIQUE(clinic_id, whatsapp_number)` constraint on patients means the same phone number CAN exist in multiple clinics. This is intentional — same patient, different clinics.
- `conversation_sessions` also has one row per `(clinic_id, whatsapp_number)`. A completed consent session must be reused for later diagnostic flows rather than inserting a new row.

### Python Import Path
- Keep `pytest.ini` with `pythonpath = .`. Without it, Python may import an unrelated `app` package from another workspace path instead of this repo's local `app/` package.
- Keep `tzdata` in `requirements.txt`. Windows virtualenvs need it for `ZoneInfo("Asia/Kolkata")`; Linux/macOS may get timezone data from the OS and hide the missing dependency.

### Local Docker
- Docker Compose is the supported local Postgres/Redis path, but tests cannot start services if Docker Desktop's Linux engine is not running. Start Docker Desktop before running the full local CI path.
- Local Compose PostgreSQL uses host port `55432`, not `5432`, to avoid connecting tests to a different local Postgres installation.
- Local Compose intentionally persists PostgreSQL only. Redis is an ephemeral cache; do not add a Redis volume unless its source-of-truth role is deliberately changed.

### CI/CD Config
- Quote the GitHub Actions `"on"` key if tests parse workflow YAML with PyYAML; unquoted `on` is treated as boolean YAML 1.1 by PyYAML.
- Quote `"$schema"` in `railway.toml`; TOML bare keys cannot start with `$`.

### Runtime Integration
- Incoming WhatsApp and failed-message retry paths use the shared runtime flow dispatcher for consent, owner commands, and diagnostics flows.
- `app/main.py` starts the in-process APScheduler instance during application lifespan and writes `scheduler:heartbeat` on startup. Keep one backend replica for the MVP scheduler model.
- `POST /api/v1/report-ready` is owner-authenticated because it sends patient report documents; LIMS-specific machine authentication remains outside this pilot.
- Automated report delivery paths must reject patients with `opt_in=False`; staff use manual sharing after opt-out.
- `Settings.api_v1_prefix` exists, but `app/api/v1/__init__.py` currently mounts the router with a literal `"/api/v1"` prefix. Changing the environment setting alone will not move API routes.

---

## ENVIRONMENT SETUP (for new dev sessions)

```bash
# 1. Copy env file
cp .env.example .env
# Fill in: DATABASE_URL, REDIS_URL, WA_APP_SECRET, WA_VERIFY_TOKEN, GROQ_API_KEY,
#          SUPABASE_URL, SUPABASE_SERVICE_KEY

# 2. Create local virtualenv and install dependencies
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 3. Run migrations
.\.venv\Scripts\python.exe -m alembic upgrade head

# 4. Seed pilot clinic
.\.venv\Scripts\python.exe scripts/seed_pilot.py

# 5. Start dev server
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000

# 6. Expose webhook for local testing (requires ngrok or similar)
ngrok http 8000
# Register the ngrok URL in Meta dashboard as webhook URL
```

---

## COMMIT CONVENTIONS
Every completed task in docs/project/tasks.md gets one atomic commit. Format:

```
type(scope): short description

feat(webhook): add idempotency check for incoming WA messages
feat(models): add TimestampMixin and SoftDeleteMixin to base
fix(cache): invalidate clinic cache on settings update
test(webhook): add duplicate message rejection test
chore(migrations): initial schema migration with all 14 tables
```

Types: `feat`, `fix`, `test`, `refactor`, `chore`, `docs`

---
