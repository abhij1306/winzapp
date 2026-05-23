# Tasks

Canonical execution board. One task should fit one focused Codex session and one atomic commit once this folder is a Git repo.

## Sprint 1: Core Infrastructure

### S1-T01: Project scaffolding, config, and local services
- [ ] Status: pending

Build FastAPI app shell, settings, health endpoint, Docker Compose local Postgres/Redis, base test config, lint/type config, and `.env.example`.

Acceptance criteria:
- `docker compose up -d postgres redis` starts local services.
- `uvicorn app.main:app --reload --port 8000` starts.
- `GET /health` returns `{"status": "ok"}` before DB checks are wired.
- `pytest`, `mypy app/`, and `ruff check app/` run cleanly.
- `.env.example` includes `LLM_PROVIDER`, `LLM_MODEL`, and `GROQ_API_KEY`.

Test requirement: `tests/test_health.py`.

### S1-T02: Async database and Alembic setup
- [ ] Status: pending

Build SQLAlchemy 2.0 async engine/session, `get_db`, Alembic env, and test DB fixtures against real Postgres.

Acceptance criteria:
- AsyncSession is used everywhere.
- Alembic imports app model metadata.
- Test fixture creates isolated test schema/database.
- Local CI can run `alembic upgrade head`.

Test requirement: DB fixture smoke test.

### S1-T03: SQLAlchemy base mixins
- [ ] Status: pending

Create `TimestampMixin` and `SoftDeleteMixin`.

Acceptance criteria:
- UUID primary key, `created_at`, `updated_at`.
- `deleted_at`, `deleted_by`, `is_deleted`.
- `updated_at` has server default and on-update behavior.

Test requirement: `tests/test_models/test_base_mixins.py`.

### S1-T04: SQLAlchemy models
- [ ] Status: pending

Create all Pilot MVP schema models: `Clinic`, `Doctor`, `Patient`, `AppointmentSlot`, `Appointment`, `Test`, `TestBooking`, `ConversationSession`, `Message`, `FailedMessage`, `AuditLog`, `RecallSchedule`, `Review`, `Broadcast`.

Acceptance criteria:
- All 14 models import from `app.models`.
- Tenant tables include `clinic_id`.
- Relationships use `lazy="selectin"` or `lazy="noload"`.
- Patient has unique `(clinic_id, whatsapp_number)`.
- Appointment models are included but appointment conversation flows remain Post-pilot.

Test requirement: `tests/test_models/test_model_fields.py`.

### S1-T05: Initial migration with RLS and triggers
- [ ] Status: pending

Create initial schema migration.

Acceptance criteria:
- `pgcrypto` extension enabled.
- `set_updated_at()` trigger attached to mutable tables.
- All 14 tables exist.
- Required indexes and unique constraints exist.
- RLS enabled on tenant patient/booking/session/message tables.

Test requirement: `tests/test_migrations/test_schema.py`.

### S1-T06: Common and WhatsApp Pydantic schemas
- [ ] Status: pending

Create shared response schemas and WhatsApp webhook payload schemas.

Acceptance criteria:
- Error envelope and paginated response schemas exist.
- WhatsApp payload validates `object == "whatsapp_business_account"`.
- `from` is aliased as `from_`.
- Unsupported message types are rejected.

Test requirement: `tests/test_schemas/test_whatsapp_schemas.py` and `tests/test_schemas/test_common_schemas.py`.

### S1-T07: Redis cache service
- [ ] Status: pending

Build cache helpers for clinic config, test catalog, and conversation sessions.

Acceptance criteria:
- Redis values are JSON serialized.
- Session values always use TTL.
- Cache misses fall back to DB.
- Redis failures degrade to DB reads where possible.
- Session write-through API exists.

Test requirement: `tests/test_services/test_cache.py` using real Redis test instance.

### S1-T08: Utilities, structured logging, and audit service
- [ ] Status: pending

Build phone normalization/masking, IST datetime helpers, structlog setup, and `write_audit()`.

Acceptance criteria:
- Logs never include full patient phone numbers.
- Audit helper validates actor type and does not break primary operation on failure.
- All state-changing tasks have a clear audit path.

Test requirement: `tests/test_utils/test_phone.py` and `tests/test_services/test_audit.py`.

### S1-T09: Feature flags and LLM service abstraction
- [ ] Status: pending

Build `require_feature()` and `app/services/llm_service.py` with Groq default provider configuration.

Acceptance criteria:
- Feature flags read through clinic cache.
- Disabled/missing flags return error envelope with 403.
- LLM provider/model/API key load from settings.
- Public functions are provider-neutral: `classify_intent()` and `draft_review_reply()`.
- LLM failures do not crash webhook flow.

Test requirement: `tests/test_services/test_feature_flags.py` and `tests/test_services/test_llm_service.py`.

### S1-T10: WhatsApp sender service
- [ ] Status: pending

Build async send helpers for text, list, buttons, document, and template messages.

Acceptance criteria:
- Uses `httpx.AsyncClient`.
- Enforces 10 list items per section and 3 buttons.
- Raises `WADeliveryError` on Meta API failure.
- External calls are mocked in tests.

Test requirement: `tests/test_services/test_whatsapp_sender.py`.

### S1-T11: Flow engine base and consent flow
- [ ] Status: pending

Build flow base interface, session state conventions, templates module, and explicit consent flow.

Acceptance criteria:
- First patient message triggers consent before other automation.
- Consent yes/no updates patient and audit log.
- Refusal stops further automation.
- Session state persists via cache service.

Test requirement: `tests/test_flows/test_consent_flow.py`.

### S1-T12: WhatsApp webhook handler
- [ ] Status: pending

Build the webhook entrypoint.

Acceptance criteria:
- GET verification challenge works.
- Invalid signatures return 403.
- Duplicate `wa_message_id` is silently ACKed.
- Inbound message is written before flow engine.
- Flow exceptions write `failed_messages` and return 200.
- Valid messages can route and respond.

Test requirement: `tests/test_webhook/test_whatsapp_webhook.py`.

### S1-T13: Local CI, GitHub Actions, and Railway skeleton
- [ ] Status: pending

Create local CI script/docs, GitHub Actions workflow with Postgres/Redis services, Dockerfile, and Railway config.

Acceptance criteria:
- Local CI command runs migrations, pytest, mypy, and ruff.
- GitHub Actions runs the same checks on push/PR.
- Railway config documents one web replica with in-process scheduler.
- Health endpoint reports DB and Redis status once services are wired.

Test requirement: CI workflow dry-run where possible plus health test.

### S1-T14: Pilot seed data and Meta template registration scaffold
- [ ] Status: pending

Create idempotent seed scripts for the pilot diagnostics clinic and test catalog, plus a scaffold for Meta template registration.

Acceptance criteria:
- Seed script creates one clinic and 12 tests.
- Running seed twice does not duplicate data.
- Feature flags match diagnostics Pilot MVP.
- Template registration script is safe to run in dry-run mode.

Test requirement: `tests/test_scripts/test_seed_pilot.py`.

## Sprint 2: Diagnostics Conversation and Report Delivery

### S2-T01: Rule-first diagnostics intent router
- [ ] Status: pending; blocked by S1-T12

Classify diagnostics intents: test booking, report inquiry, home collection, cancel, admin, unknown. LLM fallback is feature-flagged.

Test requirement: `tests/test_services/test_intent_router.py`.

### S2-T02: Diagnostics test booking walk-in flow
- [ ] Status: pending; blocked by S2-T01

Category, test selection, confirmation, booking creation, audit, session clear.

Test requirement: `tests/test_flows/test_test_booking_flow.py`.

### S2-T03: Diagnostics home collection flow
- [ ] Status: pending; blocked by S2-T02

Address/location capture, morning slot selection, fasting flag handling, booking creation.

Test requirement: `tests/test_flows/test_home_collection_flow.py`.

### S2-T04: Report inquiry and cancellation flows
- [ ] Status: pending; blocked by S2-T02

Support report status inquiry and soft-cancel bookings with audit log.

Test requirement: `tests/test_flows/test_report_and_cancel_flows.py`.

### S2-T05: Admin WhatsApp diagnostics commands
- [ ] Status: pending; blocked by S2-T02

Commands: today's tests, pending reports, send report, cancel booking, daily stats.

Test requirement: `tests/test_flows/test_admin_flow.py`.

### S2-T06: Storage service and report-ready API
- [ ] Status: pending; blocked by S2-T02

Upload/pass-through report PDF, create 24-hour signed URL, send WhatsApp document, update booking, audit, create recall where relevant.

Test requirement: `tests/test_api/test_report_ready.py`.

### S2-T07: Recall scheduling engine
- [ ] Status: pending; blocked by S2-T06

Create recall schedules for HbA1c, thyroid, full body, and annual checkup rules.

Test requirement: `tests/test_services/test_recall_scheduling.py`.

### S2-T08: Message template registration and reminder readiness
- [ ] Status: pending; blocked by S1-T14

Prepare Meta templates for fasting reminders, recall reminders, review requests, and daily digest.

Test requirement: dry-run template payload validation.

## Sprint 3: Automation, Dashboard, and Pilot Launch

### S3-T01: OTP auth API
- [ ] Status: pending; blocked by S1-T10

Implement owner OTP send/verify and short-lived JWT.

Test requirement: `tests/test_api/test_auth_otp.py`.

### S3-T02: Clinic settings API
- [ ] Status: pending; blocked by S3-T01

Get/update clinic settings with cache invalidation and audit.

Test requirement: `tests/test_api/test_clinic_settings.py`.

### S3-T03: Test booking operations API
- [ ] Status: pending; blocked by S3-T01

List, filter, update, create, and soft-delete test bookings.

Test requirement: `tests/test_api/test_test_bookings.py`.

### S3-T04: Pending reports upload API
- [ ] Status: pending; blocked by S2-T06

Dashboard upload path for report PDF delivery.

Test requirement: `tests/test_api/test_report_upload.py`.

### S3-T05: Patient and test catalog APIs
- [ ] Status: pending; blocked by S3-T01

Pilot dashboard support for patients and test catalog maintenance.

Test requirement: `tests/test_api/test_patients.py` and `tests/test_api/test_tests.py`.

### S3-T06: Failed message inbox and retry API
- [ ] Status: pending; blocked by S1-T12

List unresolved failed messages and replay payloads through flow engine.

Test requirement: `tests/test_api/test_failed_messages.py`.

### S3-T07: Scheduler jobs
- [ ] Status: pending; blocked by S2-T07

Implement fasting reminders, review requests, recall reminders, daily digest, and scheduler heartbeat. Appointment jobs remain Post-pilot.

Test requirement: `tests/test_scheduler/test_scheduler_jobs.py`.

### S3-T08: Minimal dashboard frontend
- [ ] Status: pending; blocked by S3-T01..S3-T06

Build OTP login, overview, test bookings, pending reports/upload, failed messages/retry, and settings pages.

Test requirement: component tests plus one browser smoke path.

### S3-T09: Observability and alerting
- [ ] Status: pending; blocked by S3-T07

Add Sentry/Logfire wiring, structured log fields, webhook latency alert, WA delivery failure alert, missed scheduler heartbeat alert.

Test requirement: config smoke tests and manual alert checklist.

### S3-T10: Pilot launch checklist
- [ ] Status: pending; blocked by all S1-S3 tasks

Run local CI, deployed smoke tests, WhatsApp round trip, idempotency test, report delivery test, failed-message retry test, and RLS isolation test.

Test requirement: completed `docs/ci-cd/release-checklist.md`.

## Definition of Done

Every task must satisfy:

1. Acceptance criteria pass.
2. Required tests exist and pass.
3. Full `pytest` passes.
4. `mypy app/` passes.
5. `ruff check app/` passes.
6. Relevant docs are updated.
7. AGENTS.md sprint state is updated.
8. Commit is atomic once the repo is initialized locally.
