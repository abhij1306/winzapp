# Product Requirements

Source archive: [docs/archive/whatsapp_clinic_suite_FINAL_spec_v2.0.md](../archive/whatsapp_clinic_suite_FINAL_spec_v2.0.md)

This is the living requirements document. The archived spec is historical input, not active canon.

## Phases

- `Pilot MVP`: required for the first diagnostics-clinic pilot.
- `Post-pilot`: required for the SaaS product after the pilot proves core value.
- `Future/Backlog`: known product direction, not required for initial scale-up.

## Product Scope

| ID | Requirement | Phase | Notes |
|---|---|---:|---|
| PRD-001 | Patients interact through WhatsApp only. | Pilot MVP | No patient app, portal, SMS, or email fallback. |
| PRD-002 | Owners/staff can use a minimal web dashboard for operations. | Pilot MVP | OTP login, overview, bookings, pending reports, failed messages, settings. |
| PRD-003 | Owner/admin WhatsApp commands are supported. | Pilot MVP | Diagnostics commands first. |
| PRD-004 | GP appointment booking conversation flows are supported. | Post-pilot | Appointment data model remains Pilot MVP. |
| PRD-005 | Multi-clinic SaaS tenant model is supported. | Pilot MVP | `clinic_id` on every tenant-scoped table. |
| PRD-006 | Mixed clinic type flows are supported. | Post-pilot | Pilot assumes one primary clinic type per clinic. |

## Non-Functional Requirements

| ID | Requirement | Phase | Acceptance Target |
|---|---|---:|---|
| NFR-001 | Webhook ACK latency. | Pilot MVP | p95 under 500 ms. |
| NFR-002 | Patient-visible message latency. | Pilot MVP | p95 under 2 seconds after ACK path. |
| NFR-003 | Scheduler drift. | Pilot MVP | Under 5 minutes from configured time. |
| NFR-004 | Uptime target. | Post-pilot | 99.5 percent monthly. |
| NFR-005 | Duplicate WhatsApp webhook messages are silently ACKed. | Pilot MVP | Idempotency by `wa_message_id`. |
| NFR-006 | Failed inbound messages are retained and retryable. | Pilot MVP | `failed_messages` dead-letter queue. |
| NFR-007 | Concurrent conversations per clinic. | Post-pilot | 500 simultaneous sessions. |
| NFR-008 | Report volume per diagnostics clinic. | Post-pilot | 500 PDFs/day. |
| NFR-009 | Message log retention. | Pilot MVP | 90 days, configurable. |
| NFR-010 | Report retention. | Pilot MVP | 2 years minimum. |
| NFR-011 | Audit retention. | Pilot MVP | 7 years. |
| NFR-012 | Patient phone numbers are masked in logs. | Pilot MVP | Last 4 digits only. |

## Platform Requirements

| ID | Requirement | Phase | Notes |
|---|---|---:|---|
| PLAT-001 | Backend uses FastAPI async on Python 3.11+. | Pilot MVP | Async all the way down. |
| PLAT-002 | Database uses PostgreSQL with SQLAlchemy 2.0 async and Alembic. | Pilot MVP | Supabase for MVP, self-hosted later. |
| PLAT-003 | Redis is mandatory from day one. | Pilot MVP | Sessions, clinic config, test catalog. |
| PLAT-004 | Scheduler uses APScheduler in-process for Pilot MVP. | Pilot MVP | One Railway web replica only. |
| PLAT-005 | Scheduler moves to worker/Celery-style execution. | Post-pilot | Required before multi-replica scaling. |
| PLAT-006 | WhatsApp uses Meta Cloud API directly. | Pilot MVP | No BSP. |
| PLAT-007 | LLM service uses a small provider abstraction with Groq as default. | Pilot MVP | Provider/model/API key loaded from `.env`. |
| PLAT-008 | Storage uses Supabase Storage behind `app/services/storage.py`. | Pilot MVP | Abstract for future S3 migration. |
| PLAT-009 | JWT plus OTP login for owners/staff. | Pilot MVP | No passwords. |
| PLAT-010 | Razorpay subscription billing. | Post-pilot | Pilot uses manual/free-trial activation. |
| PLAT-011 | React, Vite, Tailwind dashboard. | Pilot MVP | Narrow operations dashboard only. |
| PLAT-012 | Railway deployment path. | Pilot MVP | Primary MVP execution path. |
| PLAT-013 | Hetzner plus Docker Compose production path. | Post-pilot | Document from day one. |

## Data Requirements

| ID | Requirement | Phase | Notes |
|---|---|---:|---|
| DATA-001 | SQLAlchemy base mixins for UUID, timestamps, and soft delete. | Pilot MVP | Mutable models use soft delete. |
| DATA-002 | Clinic model with JSONB settings and feature flags. | Pilot MVP | Includes WhatsApp phone number mapping. |
| DATA-003 | Patient model with per-clinic unique WhatsApp number. | Pilot MVP | Same number may exist in multiple clinics. |
| DATA-004 | Doctor, appointment slot, and appointment models. | Pilot MVP | Data model only; GP flow is Post-pilot. |
| DATA-005 | Test catalog and test booking models. | Pilot MVP | Core diagnostics flow. |
| DATA-006 | Conversation session model. | Pilot MVP | DB source of truth, Redis fast path. |
| DATA-007 | Message and failed message models. | Pilot MVP | Idempotency and dead-letter queue. |
| DATA-008 | Audit log model. | Pilot MVP | Required for all state changes. |
| DATA-009 | Recall schedule model. | Pilot MVP | Needed after report delivery for repeat care. |
| DATA-010 | Review model. | Pilot MVP | Review collection now, GBP autopilot later. |
| DATA-011 | Broadcast model. | Post-pilot | Feature-flagged. |
| DATA-012 | RLS enabled on tenant patient/booking/session/message tables. | Pilot MVP | App also filters by `clinic_id`. |
| DATA-013 | `pgcrypto` extension and `set_updated_at()` trigger. | Pilot MVP | Migration must create both. |

## WhatsApp Requirements

| ID | Requirement | Phase | Notes |
|---|---|---:|---|
| WA-001 | Webhook GET verification challenge. | Pilot MVP | Meta setup requirement. |
| WA-002 | POST signature verification. | Pilot MVP | Reject invalid signatures with 403. |
| WA-003 | Idempotency before processing. | Pilot MVP | Check `messages.wa_message_id`. |
| WA-004 | Write inbound message before flow execution. | Pilot MVP | Write-first invariant. |
| WA-005 | Dead-letter on flow exception while returning 200 to Meta. | Pilot MVP | Prevent retry storms. |
| WA-006 | Pydantic schemas validate webhook payloads. | Pilot MVP | `from` aliased as `from_`. |
| WA-007 | Send text, list, buttons, document, and template messages. | Pilot MVP | External calls mocked in tests. |
| WA-008 | Enforce interactive list and button limits. | Pilot MVP | 10 list items per section, 3 buttons. |
| WA-009 | Register Meta templates. | Pilot MVP | Required before reminders and review requests. |
| WA-010 | Meta Embedded Signup for clinics. | Post-pilot | Manual setup acceptable for pilot. |

## Conversation Requirements

| ID | Requirement | Phase | Notes |
|---|---|---:|---|
| FLOW-001 | Rule-first intent router. | Pilot MVP | Diagnostics intents first. |
| FLOW-002 | LLM fallback for unknown intent when feature flag is enabled. | Pilot MVP | Groq default provider. |
| FLOW-003 | First-ever patient message runs consent flow. | Pilot MVP | Explicit opt-in before automation. |
| FLOW-004 | Diagnostics test booking walk-in flow. | Pilot MVP | Category, test, confirm. |
| FLOW-005 | Diagnostics home collection flow. | Pilot MVP | Address or location pin plus slot. |
| FLOW-006 | Report inquiry flow. | Pilot MVP | Basic booking/report status. |
| FLOW-007 | Cancel flow. | Pilot MVP | Soft-cancel booking and audit. |
| FLOW-008 | Admin WhatsApp command flow. | Pilot MVP | Diagnostics owner commands. |
| FLOW-009 | GP appointment booking flow. | Post-pilot | Not part of diagnostics pilot. |
| FLOW-010 | Mixed clinic routing. | Post-pilot | Feature-flagged after both flows stabilize. |

## API Requirements

All endpoints are tracked in [traceability.md](traceability.md). Pilot MVP execution tasks cover only endpoints needed by the diagnostics pilot dashboard and flows.

| ID | Requirement | Phase |
|---|---|---:|
| API-001 | Standard success and error envelopes. | Pilot MVP |
| API-002 | OTP auth send and verify. | Pilot MVP |
| API-003 | Clinic read/update settings. | Pilot MVP |
| API-004 | Test booking list/create/update/report upload/soft delete. | Pilot MVP |
| API-005 | Report-ready endpoint. | Pilot MVP |
| API-006 | Patient list/profile/update. | Pilot MVP |
| API-007 | Test catalog list/add/edit/soft delete. | Pilot MVP |
| API-008 | Failed message list and retry. | Pilot MVP |
| API-009 | Dashboard stats. | Pilot MVP |
| API-010 | Appointment APIs. | Post-pilot |
| API-011 | Slot APIs. | Post-pilot |
| API-012 | Review GBP approve/post APIs. | Post-pilot |
| API-013 | Broadcast APIs. | Post-pilot |
| API-014 | Clinic registration API and onboarding wizard backend. | Post-pilot |

## Automation Requirements

| ID | Requirement | Phase | Notes |
|---|---|---:|---|
| AUTO-001 | Fasting reminder job at 8 PM IST. | Pilot MVP | Diagnostics bookings only. |
| AUTO-002 | Review request job. | Pilot MVP | Collect review link/request; no GBP autopilot. |
| AUTO-003 | Recall scheduling after report delivery. | Pilot MVP | HbA1c, thyroid, full body, annual checkup. |
| AUTO-004 | Recall reminder job. | Pilot MVP | Feature-flagged. |
| AUTO-005 | Daily digest to owner at 9 AM IST. | Pilot MVP | Diagnostics stats. |
| AUTO-006 | No-show marking. | Post-pilot | More relevant after appointment flows. |
| AUTO-007 | Appointment reminders. | Post-pilot | GP flow deferred. |
| AUTO-008 | GBP review fetch job. | Post-pilot | Feature-flagged. |
| AUTO-009 | Scheduler heartbeat. | Pilot MVP | Observability. |

## Report Requirements

| ID | Requirement | Phase | Notes |
|---|---|---:|---|
| REP-001 | Manual report upload from dashboard. | Pilot MVP | Core operations workflow. |
| REP-002 | Report-ready API supports PDF URL or base64. | Pilot MVP | One required. |
| REP-003 | Store PDFs under clinic and booking path. | Pilot MVP | Supabase Storage. |
| REP-004 | Signed report URLs last 24 hours. | Pilot MVP | Patients may open later. |
| REP-005 | Send WhatsApp document with caption. | Pilot MVP | Uses sender service. |
| REP-006 | Update booking status and audit delivery. | Pilot MVP | `report.delivered`. |
| REP-007 | Password-protected PDFs. | Post-pilot | Requires DOB workflow; not MVP. |

## Dashboard Requirements

| ID | Requirement | Phase | Notes |
|---|---|---:|---|
| UI-001 | OTP login page. | Pilot MVP | Owner/staff only. |
| UI-002 | Today overview dashboard. | Pilot MVP | Bookings, reports, failed messages. |
| UI-003 | Test bookings page. | Pilot MVP | List, filter, update. |
| UI-004 | Pending reports page with upload. | Pilot MVP | Critical operations path. |
| UI-005 | Failed messages inbox and retry. | Pilot MVP | Dead-letter operations. |
| UI-006 | Settings page. | Pilot MVP | Clinic config, feature flags. |
| UI-007 | Review monitor with GBP approval. | Post-pilot | GBP feature. |
| UI-008 | Broadcast UI. | Post-pilot | Feature-flagged. |
| UI-009 | Onboarding wizard. | Post-pilot | Manual pilot setup first. |

## Security and Compliance Requirements

| ID | Requirement | Phase |
|---|---|---:|
| SEC-001 | Explicit patient consent before automated flows. | Pilot MVP |
| SEC-002 | Opt-out stops automated messages. | Pilot MVP |
| SEC-003 | JWT access tokens are short-lived. | Pilot MVP |
| SEC-004 | Secrets loaded from environment only. | Pilot MVP |
| SEC-005 | Secret rotation documented. | Pilot MVP |
| SEC-006 | Rate limits for webhook and API endpoints. | Post-pilot |
| SEC-007 | TLS in production. | Pilot MVP |
| SEC-008 | Audit every state-changing operation. | Pilot MVP |

## Observability Requirements

| ID | Requirement | Phase |
|---|---|---:|
| OBS-001 | Structured logs with request and clinic context. | Pilot MVP |
| OBS-002 | PII masking in logs. | Pilot MVP |
| OBS-003 | Health endpoint checks DB, Redis, and scheduler. | Pilot MVP |
| OBS-004 | Alert on webhook latency. | Pilot MVP |
| OBS-005 | Alert on WhatsApp delivery failures. | Pilot MVP |
| OBS-006 | Alert on missed scheduler heartbeat. | Pilot MVP |
| OBS-007 | Sentry or Logfire integration. | Pilot MVP |
