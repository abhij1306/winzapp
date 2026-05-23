# WhatsApp-Native Clinic & Diagnostics Suite — Build Spec
### v2.0 | May 2026 | For Codex / AI-Assisted Development

---

## TABLE OF CONTENTS
1. [Project Overview & Non-Functional Requirements](#1-project-overview--non-functional-requirements)
2. [Tech Stack Decision Matrix](#2-tech-stack-decision-matrix)
3. [Recommended Stack](#3-recommended-stack)
4. [System Architecture](#4-system-architecture)
5. [Database Schema](#5-database-schema)
6. [WhatsApp Cloud API Integration](#6-whatsapp-cloud-api-integration)
7. [Conversation Flows — Complete State Machine](#7-conversation-flows--complete-state-machine)
8. [Backend API Endpoints](#8-backend-api-endpoints)
9. [Caching Layer](#9-caching-layer)
10. [Scheduler & Automation Engine](#10-scheduler--automation-engine)
11. [Report PDF Delivery System](#11-report-pdf-delivery-system)
12. [Google Business Profile (GBP) Autopilot](#12-google-business-profile-gbp-autopilot)
13. [Feature Flags](#13-feature-flags)
14. [Admin Dashboard (Minimal Web UI)](#14-admin-dashboard-minimal-web-ui)
15. [Onboarding Flow](#15-onboarding-flow)
16. [Security, Compliance & Data Handling](#16-security-compliance--data-handling)
17. [Observability & Alerting](#17-observability--alerting)
18. [Environment Variables & Config](#18-environment-variables--config)
19. [Deployment — Options & Recommendation](#19-deployment--options--recommendation)
20. [MVP Scope for Pilot (Diagnostic Centre)](#20-mvp-scope-for-pilot-diagnostic-centre)
21. [File & Folder Structure](#21-file--folder-structure)
22. [Third-Party Services](#22-third-party-services)
23. [Testing Strategy](#23-testing-strategy)
24. [INVARIANTS.md — Project Onboarding File](#24-invariantsmd--project-onboarding-file)
25. [Launch Checklist](#25-launch-checklist)

---

## 1. Project Overview & Non-Functional Requirements

### What This Is
A **WhatsApp-first SaaS product** for independent clinics and diagnostic laboratories in India. It replaces phone-based appointment booking, manual report delivery, and forgotten follow-ups with fully automated WhatsApp conversations. No mobile app. No desktop dashboard required for day-to-day operations. The entire patient-side and doctor-side experience runs through WhatsApp.

### Primary ICP for Pilot
- **Diagnostic centers / pathology labs** (standalone, Tier 2 India)
- **GP clinics** (single doctor, 1 receptionist or none)

### Core Value Propositions
1. Test booking via WhatsApp → confirmation → home collection coordination
2. Automated report PDF delivery to patient's WhatsApp
3. Appointment reminders → 40–60% reduction in no-shows
4. Post-visit review collection → Google rating improvement
5. Recall reminders → repeat revenue (diabetics, thyroid, HbA1c patients)
6. Doctor/owner manages via WhatsApp commands — no login required

### What This Is NOT
- Not a clinical decision support tool
- Not an EMR / full clinic management system
- Not a replacement for Practo/1mg
- Not a prescription management tool

### Non-Functional Requirements

```
PERFORMANCE
├── Webhook ACK latency:         < 500ms (WhatsApp SLA: respond within 20s)
├── End-to-end message latency:  < 2s per message (patient-visible)
└── Scheduler job drift:         < 5 min from scheduled time

RELIABILITY
├── Uptime target:               99.5% monthly (≈ 3.6 hrs downtime/month)
├── Webhook idempotency:         Duplicate WA messages must be silently discarded
└── Failed messages:             Dead-letter queue with retry; never lost

SCALABILITY
├── Concurrent conversations:    500 simultaneous active sessions per clinic
├── Multi-tenant isolation:      Every DB query filtered by clinic_id; RLS enforced
└── Report PDFs:                 Up to 500 documents/day per diagnostic centre

DATA & COMPLIANCE
├── Message log retention:       90 days (configurable)
├── Report file retention:       2 years minimum
├── Audit log retention:         7 years (DPDP Act traceability)
└── PII in logs:                 Patient phone numbers masked to last 4 digits only

SECURITY
├── All data in transit:         TLS 1.2+
├── Multi-tenant:                Row-level security in Postgres + clinic_id filter on every query
└── Secrets:                     No secrets in code; env vars only; rotation documented
```

---

## 2. Tech Stack Decision Matrix

### Backend Framework Options

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **FastAPI (Python)** | Fast, async, easy WA webhook, great LLM integration | Needs gunicorn/uvicorn setup | ✅ Recommended |
| Express.js (Node) | Fast, huge ecosystem | Callback complexity for flows | ✅ Also viable |
| Django (Python) | Batteries included, admin panel free | Heavier, overkill for webhooks | ⚠️ Only if team knows Django |
| NestJS (Node) | Structured, TypeScript | Steep learning curve | ⚠️ Skip for MVP |

### Database Options

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **PostgreSQL** | Relational, JSONB, RLS, reliable | Needs hosting | ✅ Recommended |
| SQLite | Zero setup, great for dev | Not for multi-tenant prod | ✅ Dev only |
| MongoDB | Flexible schema | Less structured for appointments | ⚠️ Conversation logs only |
| Supabase (managed Postgres) | Free tier, auth built-in, RLS dashboard | Vendor lock-in | ✅ Great for MVP speed |

### Scheduler Options

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **APScheduler (Python)** | Simple, in-process, zero infra | Not for high volume | ✅ MVP choice |
| Celery + Redis | Production-grade, distributed | Redis hosting cost | ✅ Scale-up option |
| Inngest | Serverless-friendly | Paid at scale | ✅ Good on Vercel |

### Hosting Options

| Option | Monthly Cost | Verdict |
|---|---|---|
| Railway.app | ~$10–20 | ✅ MVP recommended |
| Render.com | Free → $7 | ✅ Good fallback |
| **Hetzner CX21 VPS** | €5.77 ≈ ₹540 | ✅ Production recommended |
| DigitalOcean App Platform | $12–25 | ⚠️ Pricier |

---

## 3. Recommended Stack

```
Backend:          FastAPI (Python 3.11+)
Database:         PostgreSQL (Supabase for MVP, self-hosted for prod)
ORM:              SQLAlchemy 2.0 (async) + Alembic (migrations)
Cache:            Redis — used from Day 1 (sessions, clinic config, test catalog)
Task Queue:       APScheduler (MVP) → Celery + Redis (scale)
WhatsApp API:     Meta WhatsApp Cloud API (direct, no BSP)
File Storage:     Supabase Storage or AWS S3 (PDF reports)
PDF:              ReportLab / WeasyPrint (generate) or pass-through from LIMS
LLM:              Claude claude-sonnet-4-20250514 (intent parsing + review replies)
Payments:         Razorpay (subscriptions)
Deployment:       Railway.app (MVP) → Hetzner VPS + Docker Compose (prod)
Dashboard:        React (Vite) + Tailwind CSS
Auth:             Supabase Auth or JWT + OTP (no password login for owners)
GBP:              Google My Business API (OAuth2)
Observability:    Structured JSON logs → Logfire or Sentry + custom alerting
```

---

## 4. System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         PATIENT SIDE                             │
│  Patient WhatsApp ──► Meta Cloud API ──► Webhook (FastAPI)       │
└────────────────────────────────────────────────────┬─────────────┘
                                                     │
                                        ┌────────────▼────────────┐
                                        │      FastAPI Server      │
                                        │                          │
                                        │  ① Signature verify      │
                                        │  ② Idempotency check     │
                                        │  ③ Log message           │
                                        │  ④ Intent Router         │
                                        │     (rule-based + LLM)   │
                                        │  ⑤ Flow Engine           │
                                        │     (state machine)      │
                                        └──────┬─────────┬─────────┘
                                               │         │
                              ┌────────────────▼──┐  ┌───▼────────────┐
                              │   PostgreSQL DB    │  │  Redis Cache   │
                              │                   │  │                │
                              │ - clinics         │  │ - clinic cfg   │
                              │ - patients        │  │ - conv session │
                              │ - appointments    │  │ - test catalog │
                              │ - test_bookings   │  └────────────────┘
                              │ - conversations   │
                              │ - audit_log       │  ┌────────────────┐
                              │ - failed_messages │  │  File Storage  │
                              └───────────────────┘  │  (S3/Supabase) │
                                                     │  - PDFs        │
                              ┌─────────────────────►│  - images      │
                              │  APScheduler         └────────────────┘
                              │  - Reminders
                              │  - Recalls
                              │  - Review requests
                              │  - Daily digest
                              └──────────────────────

┌──────────────────────────────────────────────────────────────────┐
│                        DOCTOR/OWNER SIDE                         │
│  Owner WhatsApp ──► same webhook (role=owner → admin flow)       │
│  Web Dashboard ──► REST API (report upload, analytics, setup)    │
└──────────────────────────────────────────────────────────────────┘
```

### Key Architectural Decisions

**1. Stateful Conversation via DB + Redis**
Session state is persisted in `conversation_sessions` (Postgres) and cached in Redis (30-min TTL). The DB is the source of truth; Redis is the fast path. On cache miss, read from DB and re-populate.

**2. Single WhatsApp Number per Clinic**
Each clinic registers one WhatsApp Business number. System routes by phone_number_id on the incoming webhook.

**3. Multi-Tenant by Design**
Every DB table has a `clinic_id` foreign key. Every query filters by `clinic_id`. Row-Level Security policies in Postgres provide a second layer of enforcement.

**4. Intent Router — Rule-First, LLM-Fallback (Feature-Flagged)**
Rule-based keywords handle ~80% of inputs. Claude Haiku handles ambiguous inputs when `llm_intent_fallback` feature flag is enabled for that clinic's plan.

**5. Webhook Idempotency**
Every incoming message is checked against `messages.wa_message_id` before processing. Duplicates are silently ACK'd. Processing failures write to `failed_messages` for replay.

---

## 5. Database Schema

### SQLAlchemy Base Mixin (apply to ALL mutable tables)

```python
# app/models/base.py

from sqlalchemy import Column, DateTime, UUID, Boolean
from sqlalchemy.sql import func
import uuid

class TimestampMixin:
    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now(), nullable=False)

class SoftDeleteMixin(TimestampMixin):
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(UUID(as_uuid=True), nullable=True)

    @property
    def is_deleted(self):
        return self.deleted_at is not None
```

### PostgreSQL DDL

```sql
-- ============================================================
-- UPDATED_AT auto-trigger (apply to all mutable tables)
-- ============================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply this trigger to every table listed below.

-- ============================================================
-- MULTI-TENANT CORE
-- ============================================================

CREATE TABLE clinics (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                TEXT NOT NULL,
    owner_name          TEXT,
    clinic_type         TEXT CHECK (clinic_type IN ('gp','diagnostic','eye','dental','physio','other')),
    whatsapp_number     TEXT UNIQUE NOT NULL,   -- E.164: +919876543210
    owner_whatsapp      TEXT NOT NULL,
    address             TEXT,
    city                TEXT,
    pincode             TEXT,
    google_place_id     TEXT,
    gbp_review_link     TEXT,
    timezone            TEXT DEFAULT 'Asia/Kolkata',
    plan                TEXT DEFAULT 'starter' CHECK (plan IN ('starter','clinic','diagnostic','chain')),
    plan_active         BOOLEAN DEFAULT TRUE,
    trial_ends_at       TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ,
    deleted_by          UUID,
    settings            JSONB DEFAULT '{}'
    -- settings includes: working_hours, slot_duration_minutes, language,
    --                     home_collection, home_collection_areas,
    --                     wa_access_token, wa_phone_number_id, gbp_access_token,
    --                     features (see Section 13)
);
CREATE TRIGGER clinics_updated_at BEFORE UPDATE ON clinics
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- PATIENTS
-- ============================================================

CREATE TABLE patients (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id       UUID NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    whatsapp_number TEXT NOT NULL,
    name            TEXT,
    age             INTEGER,
    gender          TEXT CHECK (gender IN ('male','female','other',NULL)),
    address         TEXT,
    location_lat    NUMERIC(9,6),
    location_lng    NUMERIC(9,6),
    opt_in          BOOLEAN DEFAULT TRUE,
    opt_in_at       TIMESTAMPTZ,
    tags            TEXT[] DEFAULT '{}',
    last_visit_at   TIMESTAMPTZ,
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ,
    deleted_by      UUID,
    UNIQUE(clinic_id, whatsapp_number)
);
CREATE TRIGGER patients_updated_at BEFORE UPDATE ON patients
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- DOCTORS
-- ============================================================

CREATE TABLE doctors (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id       UUID NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    specialty       TEXT,
    whatsapp_number TEXT,
    is_active       BOOLEAN DEFAULT TRUE,
    slot_duration   INTEGER DEFAULT 20,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ,
    deleted_by      UUID
);
CREATE TRIGGER doctors_updated_at BEFORE UPDATE ON doctors
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- APPOINTMENT SLOTS
-- ============================================================

CREATE TABLE appointment_slots (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id       UUID NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    doctor_id       UUID REFERENCES doctors(id),
    slot_datetime   TIMESTAMPTZ NOT NULL,
    is_available    BOOLEAN DEFAULT TRUE,
    is_blocked      BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(clinic_id, doctor_id, slot_datetime)
);
CREATE TRIGGER slots_updated_at BEFORE UPDATE ON appointment_slots
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- APPOINTMENTS
-- ============================================================

CREATE TABLE appointments (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id           UUID NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    patient_id          UUID NOT NULL REFERENCES patients(id),
    doctor_id           UUID REFERENCES doctors(id),
    slot_id             UUID REFERENCES appointment_slots(id),
    appointment_type    TEXT DEFAULT 'consultation'
                        CHECK (appointment_type IN ('consultation','followup','walkin')),
    status              TEXT DEFAULT 'confirmed'
                        CHECK (status IN ('confirmed','cancelled','completed','no_show','rescheduled')),
    booked_at           TIMESTAMPTZ DEFAULT NOW(),
    appointment_at      TIMESTAMPTZ NOT NULL,
    reminder_1hr_sent   BOOLEAN DEFAULT FALSE,
    reminder_24hr_sent  BOOLEAN DEFAULT FALSE,
    review_request_sent BOOLEAN DEFAULT FALSE,
    notes               TEXT,
    cancelled_reason    TEXT,
    source              TEXT DEFAULT 'whatsapp',
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ,
    deleted_by          UUID
);
CREATE TRIGGER appointments_updated_at BEFORE UPDATE ON appointments
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE INDEX idx_appointments_clinic_date ON appointments(clinic_id, appointment_at)
  WHERE deleted_at IS NULL;

-- ============================================================
-- TEST CATALOG
-- ============================================================

CREATE TABLE tests (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id                   UUID NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    name                        TEXT NOT NULL,
    name_hindi                  TEXT,
    description                 TEXT,
    price                       NUMERIC(10,2),
    duration_hours              INTEGER DEFAULT 4,
    requires_fasting            BOOLEAN DEFAULT FALSE,
    home_collection_available   BOOLEAN DEFAULT TRUE,
    category                    TEXT,
    is_active                   BOOLEAN DEFAULT TRUE,
    sort_order                  INTEGER DEFAULT 0,
    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW(),
    deleted_at                  TIMESTAMPTZ,
    deleted_by                  UUID
);
CREATE TRIGGER tests_updated_at BEFORE UPDATE ON tests
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- TEST BOOKINGS
-- ============================================================

CREATE TABLE test_bookings (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id               UUID NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    patient_id              UUID NOT NULL REFERENCES patients(id),
    test_id                 UUID REFERENCES tests(id),
    test_name               TEXT NOT NULL,
    booking_type            TEXT DEFAULT 'walkin'
                            CHECK (booking_type IN ('walkin','home_collection')),
    status                  TEXT DEFAULT 'booked'
                            CHECK (status IN ('booked','sample_collected','processing',
                                              'report_ready','delivered','cancelled')),
    collection_address      TEXT,
    collection_lat          NUMERIC(9,6),
    collection_lng          NUMERIC(9,6),
    collection_slot         TIMESTAMPTZ,
    technician_name         TEXT,
    amount                  NUMERIC(10,2),
    payment_status          TEXT DEFAULT 'pending'
                            CHECK (payment_status IN ('pending','paid','partial')),
    payment_method          TEXT,
    report_file_path        TEXT,
    report_password         TEXT,
    report_delivered_at     TIMESTAMPTZ,
    report_status_notified  BOOLEAN DEFAULT FALSE,
    fasting_reminder_sent   BOOLEAN DEFAULT FALSE,
    booked_at               TIMESTAMPTZ DEFAULT NOW(),
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    deleted_at              TIMESTAMPTZ,
    deleted_by              UUID,
    notes                   TEXT
);
CREATE TRIGGER test_bookings_updated_at BEFORE UPDATE ON test_bookings
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE INDEX idx_test_bookings_status ON test_bookings(clinic_id, status)
  WHERE deleted_at IS NULL;

-- ============================================================
-- RECALL SCHEDULES
-- ============================================================

CREATE TABLE recall_schedules (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id       UUID NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    patient_id      UUID NOT NULL REFERENCES patients(id),
    trigger_type    TEXT NOT NULL CHECK (trigger_type IN (
                        'annual_checkup','hba1c_quarterly','thyroid_6month',
                        'lipid_annual','followup','custom')),
    trigger_at      TIMESTAMPTZ NOT NULL,
    message_template TEXT,
    status          TEXT DEFAULT 'pending'
                    CHECK (status IN ('pending','sent','responded','dismissed','snoozed')),
    snoozed_until   TIMESTAMPTZ,
    sent_at         TIMESTAMPTZ,
    response        TEXT,
    reference_id    UUID,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE TRIGGER recalls_updated_at BEFORE UPDATE ON recall_schedules
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE INDEX idx_recall_pending ON recall_schedules(trigger_at)
  WHERE status = 'pending';

-- ============================================================
-- CONVERSATION SESSIONS
-- ============================================================

CREATE TABLE conversation_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id       UUID NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    patient_id      UUID REFERENCES patients(id),
    whatsapp_number TEXT NOT NULL,
    flow            TEXT,
    step            TEXT,
    context         JSONB DEFAULT '{}',
    last_message_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at      TIMESTAMPTZ DEFAULT NOW() + INTERVAL '30 minutes',
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(clinic_id, whatsapp_number)
);
CREATE INDEX idx_session_active ON conversation_sessions(whatsapp_number, clinic_id)
  WHERE is_active = TRUE;

-- ============================================================
-- MESSAGE LOG
-- ============================================================

CREATE TABLE messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id       UUID NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    whatsapp_number TEXT NOT NULL,
    direction       TEXT CHECK (direction IN ('inbound','outbound')),
    message_type    TEXT,
    content         TEXT,
    metadata        JSONB DEFAULT '{}',
    wa_message_id   TEXT UNIQUE,      -- used for idempotency dedup
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_messages_clinic_number ON messages(clinic_id, whatsapp_number, created_at DESC);

-- ============================================================
-- FAILED MESSAGES (dead-letter queue)
-- ============================================================

CREATE TABLE failed_messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id       UUID REFERENCES clinics(id),
    whatsapp_number TEXT,
    wa_message_id   TEXT,
    raw_payload     JSONB NOT NULL,
    error           TEXT,
    retry_count     INTEGER DEFAULT 0,
    last_retry_at   TIMESTAMPTZ,
    resolved        BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- AUDIT LOG (DPDP Act traceability — 7 year retention)
-- ============================================================

CREATE TABLE audit_log (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id    UUID REFERENCES clinics(id),
    actor_id     UUID,
    actor_type   TEXT CHECK (actor_type IN ('patient','owner','staff','system')),
    action       TEXT NOT NULL,   -- 'appointment.created', 'report.delivered', etc.
    entity_type  TEXT,
    entity_id    UUID,
    diff         JSONB,           -- {before: {...}, after: {...}}
    ip_address   TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_audit_clinic ON audit_log(clinic_id, created_at DESC);

-- ============================================================
-- REVIEWS
-- ============================================================

CREATE TABLE reviews (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id        UUID NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    patient_id       UUID REFERENCES patients(id),
    source           TEXT CHECK (source IN ('google','practo','justdial')),
    rating           NUMERIC(2,1),
    review_text      TEXT,
    reviewer_name    TEXT,
    google_review_id TEXT,
    draft_reply      TEXT,
    reply_approved   BOOLEAN DEFAULT FALSE,
    reply_sent_at    TIMESTAMPTZ,
    fetched_at       TIMESTAMPTZ DEFAULT NOW(),
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- BROADCASTS
-- ============================================================

CREATE TABLE broadcasts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id       UUID NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    title           TEXT,
    message         TEXT NOT NULL,
    target_tags     TEXT[],
    status          TEXT DEFAULT 'draft'
                    CHECK (status IN ('draft','scheduled','sent','failed')),
    scheduled_at    TIMESTAMPTZ,
    sent_at         TIMESTAMPTZ,
    recipient_count INTEGER DEFAULT 0,
    delivered_count INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- ROW-LEVEL SECURITY (Postgres RLS)
-- ============================================================

ALTER TABLE patients         ENABLE ROW LEVEL SECURITY;
ALTER TABLE appointments     ENABLE ROW LEVEL SECURITY;
ALTER TABLE test_bookings    ENABLE ROW LEVEL SECURITY;
ALTER TABLE recall_schedules ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages         ENABLE ROW LEVEL SECURITY;

-- Example policy (replicate for all tables above)
CREATE POLICY clinic_isolation ON patients
  USING (clinic_id = current_setting('app.clinic_id')::UUID);

-- Set before every query in application layer:
-- await db.execute("SET app.clinic_id = :clinic_id", {"clinic_id": clinic_id})
```

---

## 6. WhatsApp Cloud API Integration

### Prerequisites
1. Meta Business Account (government ID verified)
2. WhatsApp Business API access at Meta for Developers
3. One registered phone number per clinic (can be ported from WA Business)
4. Use Meta Cloud API directly — free up to 1000 service conversations/month

### Account Setup Per Clinic
```
Option A — Embedded Signup (recommended for scale):
  Clinic owner clicks "Connect WhatsApp" on dashboard
  → Meta Embedded Signup grants permissions
  → Your app accesses their WABA, registers number
  
Option B — Manual (MVP pilot):
  Register clinic number manually in Meta Business Manager
  → OTP verification → store wa_access_token + wa_phone_number_id
     in clinics.settings JSONB
```

### Webhook Handler (FastAPI)

```python
# app/webhooks/whatsapp.py

from fastapi import APIRouter, Request, HTTPException, Query
import hmac, hashlib

router = APIRouter()
VERIFY_TOKEN = settings.WA_VERIFY_TOKEN

@router.get("/webhook/whatsapp")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge")
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return int(hub_challenge)
    raise HTTPException(status_code=403)

@router.post("/webhook/whatsapp")
async def receive_message(request: Request, db: AsyncSession = Depends(get_db)):
    raw_body = await request.body()
    body = await request.json()

    # Step 1: Verify Meta signature
    signature = request.headers.get("X-Hub-Signature-256", "")
    _verify_signature(raw_body, signature)

    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})

            for message in value.get("messages", []):
                wa_msg_id = message.get("id")
                from_number = message["from"]
                phone_number_id = value["metadata"]["phone_number_id"]

                # Step 2: Idempotency check — skip if already processed
                if await message_already_processed(db, wa_msg_id):
                    continue

                # Step 3: Log message BEFORE processing (write-first pattern)
                await log_inbound_message(db, phone_number_id, from_number,
                                          message, wa_msg_id)

                # Step 4: Dispatch to flow engine (wrapped for dead-letter safety)
                try:
                    await handle_incoming_message(
                        db=db,
                        phone_number_id=phone_number_id,
                        from_number=from_number,
                        message=message
                    )
                except Exception as e:
                    await write_failed_message(db, phone_number_id, from_number,
                                               wa_msg_id, body, str(e))

            for status in value.get("statuses", []):
                await handle_status_update(db, status)

    return {"status": "ok"}

def _verify_signature(body: bytes, signature: str):
    expected = "sha256=" + hmac.new(
        settings.WA_APP_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")
```

### Pydantic Validation for Incoming Payloads

```python
# app/schemas/whatsapp_webhook.py

from pydantic import BaseModel, validator
from typing import Optional, List

class WAMessageMetadata(BaseModel):
    phone_number_id: str
    display_phone_number: str

class WATextMessage(BaseModel):
    body: str

class WAInteractiveReply(BaseModel):
    id: str
    title: str

class WAInteractive(BaseModel):
    type: str
    list_reply: Optional[WAInteractiveReply]
    button_reply: Optional[WAInteractiveReply]

class WAMessage(BaseModel):
    id: str
    from_: str  # aliased from "from"
    type: str   # text | interactive | document | location | audio
    timestamp: str
    text: Optional[WATextMessage]
    interactive: Optional[WAInteractive]

    class Config:
        populate_by_name = True
        fields = {"from_": "from"}

    @validator("type")
    def type_must_be_supported(cls, v):
        supported = {"text", "interactive", "document", "location", "audio", "image"}
        if v not in supported:
            raise ValueError(f"Unsupported message type: {v}")
        return v

class WAWebhookPayload(BaseModel):
    object: str
    entry: List[dict]

    @validator("object")
    def must_be_whatsapp(cls, v):
        if v != "whatsapp_business_account":
            raise ValueError("Not a WhatsApp webhook")
        return v
```

### Message Sender Utilities

```python
# app/services/whatsapp_sender.py
import httpx

WA_API_URL = "https://graph.facebook.com/v18.0/{phone_number_id}/messages"

async def send_text(phone_number_id, to, text, access_token):
    async with httpx.AsyncClient() as c:
        return await c.post(
            WA_API_URL.format(phone_number_id=phone_number_id),
            headers={"Authorization": f"Bearer {access_token}"},
            json={"messaging_product": "whatsapp", "to": to,
                  "type": "text", "text": {"body": text}}
        )

async def send_interactive_list(phone_number_id, to, body_text,
                                button_text, sections, access_token):
    async with httpx.AsyncClient() as c:
        return await c.post(
            WA_API_URL.format(phone_number_id=phone_number_id),
            headers={"Authorization": f"Bearer {access_token}"},
            json={"messaging_product": "whatsapp", "to": to,
                  "type": "interactive",
                  "interactive": {
                      "type": "list",
                      "body": {"text": body_text},
                      "action": {"button": button_text, "sections": sections}
                  }}
        )

async def send_interactive_buttons(phone_number_id, to, body_text,
                                   buttons, access_token):
    """Max 3 buttons."""
    async with httpx.AsyncClient() as c:
        return await c.post(
            WA_API_URL.format(phone_number_id=phone_number_id),
            headers={"Authorization": f"Bearer {access_token}"},
            json={"messaging_product": "whatsapp", "to": to,
                  "type": "interactive",
                  "interactive": {
                      "type": "button",
                      "body": {"text": body_text},
                      "action": {"buttons": [
                          {"type": "reply",
                           "reply": {"id": b["id"], "title": b["title"]}}
                          for b in buttons
                      ]}
                  }}
        )

async def send_document(phone_number_id, to, file_url,
                        filename, caption, access_token):
    async with httpx.AsyncClient() as c:
        return await c.post(
            WA_API_URL.format(phone_number_id=phone_number_id),
            headers={"Authorization": f"Bearer {access_token}"},
            json={"messaging_product": "whatsapp", "to": to,
                  "type": "document",
                  "document": {
                      "link": file_url,
                      "filename": filename,
                      "caption": caption
                  }}
        )

async def send_template(phone_number_id, to, template_name,
                        language_code, components, access_token):
    """For proactive messages outside 24-hour window — requires Meta pre-approval."""
    async with httpx.AsyncClient() as c:
        return await c.post(
            WA_API_URL.format(phone_number_id=phone_number_id),
            headers={"Authorization": f"Bearer {access_token}"},
            json={"messaging_product": "whatsapp", "to": to,
                  "type": "template",
                  "template": {
                      "name": template_name,
                      "language": {"code": language_code},
                      "components": components
                  }}
        )
```

### Meta Templates — Pre-Register for Approval

| Template Name | Category | Usage |
|---|---|---|
| `appointment_reminder_1hr` | UTILITY | 1-hour before appointment |
| `appointment_reminder_24hr` | UTILITY | Day-before reminder |
| `appointment_confirmation` | UTILITY | Booking confirmed |
| `report_ready` | UTILITY | Lab report ready notification |
| `recall_checkup` | MARKETING | Annual/periodic recall |
| `review_request` | MARKETING | Post-visit review ask |
| `fasting_reminder` | UTILITY | Night before fasting test |

> ⚠️ App must be in **Live mode** (not Development) to message non-test users. Template approval takes 2–3 business days.

---

## 7. Conversation Flows — Complete State Machine

### Intent Router

```python
# app/services/intent_router.py

INTENT_KEYWORDS = {
    "appointment": [
        "appointment", "appoint", "doctor", "milna", "dikha",
        "booking", "book", "slot", "schedule", "visit", "consult"
    ],
    "test_booking": [
        "test", "blood", "urine", "pathology", "lab", "checkup",
        "diabetes", "thyroid", "lipid", "cbc", "khoon", "jaanch", "report"
    ],
    "report_inquiry": [
        "report", "result", "kab", "ready", "taiyar", "milega", "aaya", "pdf"
    ],
    "home_collection": [
        "ghar", "home", "collection", "aao", "aana", "bulao", "pickup"
    ],
    "cancel": [
        "cancel", "band", "nahi aana", "reschedule", "change"
    ],
    "admin": [
        "aaj ke", "kal ke", "appointments", "cancel karo",
        "report bhejo", "review report", "stats", "block slot"
    ]
}

async def route_intent(message_text: str, sender_role: str,
                       clinic_features: dict) -> str:
    if sender_role == "owner":
        return "admin"

    text = message_text.lower()
    for intent, keywords in INTENT_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return intent

    # LLM fallback — only if feature-flagged on
    if clinic_features.get("llm_intent_fallback"):
        return await llm_classify_intent(message_text)

    return "unknown"
```

### Flow: Test Booking (Diagnostic Centre)

```
Steps:
  START           → show test categories (interactive list)
  SELECT_TEST     → show specific tests in category with prices
  SELECT_TYPE     → walkin or home collection (buttons)
  GET_ADDRESS     → (home only) ask for address/location pin
  SELECT_SLOT     → show available collection/walkin slots
  CONFIRM         → show summary, confirm button
  PAYMENT         → UPI link or cash option
  DONE            → confirmation + fasting reminder if applicable

State transitions:
  START           + list_selection    → SELECT_TEST
  SELECT_TEST     + list_selection    → SELECT_TYPE
  SELECT_TYPE     + "home"            → GET_ADDRESS
  SELECT_TYPE     + "walkin"          → SELECT_SLOT
  GET_ADDRESS     + text/location     → SELECT_SLOT
  SELECT_SLOT     + list_selection    → CONFIRM
  CONFIRM         + "yes"             → PAYMENT
  CONFIRM         + "no"              → START
  PAYMENT         + any               → DONE
```

### Flow: GP Appointment Booking

```
Steps:
  START           → if multi-doctor: doctor list; else → SELECT_SLOT
  SELECT_DOCTOR   → (multi-doctor clinics only)
  SELECT_SLOT     → available slots for next 2 days
  GET_NAME        → if new patient, ask for name
  CONFIRM         → summary + confirm button
  DONE            → confirmation + Google Maps link

State transitions:
  START           + list_selection    → SELECT_SLOT (or SELECT_DOCTOR)
  SELECT_DOCTOR   + list_selection    → SELECT_SLOT
  SELECT_SLOT     + list_selection    → GET_NAME (new) or CONFIRM (known)
  GET_NAME        + text              → CONFIRM
  CONFIRM         + "confirm"         → DONE
```

### Complete Sample Flows (Hinglish)

**Test Booking:**
```
Patient: "blood test karwana hai ghar se"

Bot: Bilkul! Kaunsa test chahiye?
     [LIST: CBC ₹250 | Lipid Profile ₹450 | Diabetes Package ₹550 |
             Thyroid ₹400 | Full Body ₹1499 | Kuch aur]

Patient: [selects "Diabetes Package"]

Bot: Diabetes Package (HbA1c + FBS + PPBS) — ₹550 ✅
     Kahan se collection chahiye?
     [BUTTONS: Ghar pe aao | Main aaunga/aaungi lab]

Patient: [selects "Ghar pe aao"]

Bot: Apna address share karein, ya location pin drop karein 📍

Patient: [drops location pin]

Bot: Kal ke available morning slots:
     [LIST: 6:00 AM (fasting ke liye best) | 6:30 AM | 7:00 AM | 7:30 AM]

Patient: [selects 6:00 AM]

Bot: ✅ Booking confirmed!
     Test: Diabetes Package
     Date: Kal, 6:00 AM
     Amount: ₹550 (cash ya UPI dono chalega)
     [UPI Button: Abhi pay karein ₹550]
     
     Report taiyar hote hi WhatsApp pe milegi (4–6 ghante).
     Raat ko fasting reminder bhi aayega. 🙏
```

**Admin Commands (Doctor):**
```
Doctor: "aaj ke tests"
Bot:  📋 Aaj ke test bookings (15 Jan):
      1. Ramesh Kumar — CBC — 6:00 AM ✅ home collection
      2. Sunita Devi  — Diabetes Package — walkin 9:00 AM ✅
      3. Mohan Lal    — Lipid Profile — 7:00 AM ✅ home collection
      ...

Doctor: "report bhejo ramesh kumar"
Bot:  ✅ Ramesh Kumar ko report WhatsApp pe bhej diya.

Doctor: "aaj ka review report"
Bot:  📊 Aaj ka summary:
      📋 Tests booked: 28 (8 home, 20 walkin)
      ✅ Reports delivered: 22
      ⏳ Pending reports: 6
      ⭐ New reviews: 2 (avg 4.9)
      🔁 Recalls responded: 3
```

---

## 8. Backend API Endpoints

### Standard Response Envelopes

All API responses follow these shapes — no exceptions.

```python
# Success
{
  "data": <object or array>,
  "pagination": {             # only on paginated list endpoints
    "page": 1,
    "per_page": 20,
    "total": 143,
    "has_next": true
  }
}

# Error
{
  "error": {
    "code": "BOOKING_CONFLICT",     # machine-readable snake_case
    "message": "Slot already taken", # human-readable
    "details": {},                   # optional field-level errors
    "request_id": "uuid"             # for log correlation
  }
}
```

### Error Codes Reference

| Code | HTTP Status | Meaning |
|---|---|---|
| `SLOT_UNAVAILABLE` | 409 | Slot already booked |
| `PATIENT_NOT_FOUND` | 404 | Patient doesn't exist in clinic |
| `BOOKING_CONFLICT` | 409 | Overlapping booking |
| `PLAN_FEATURE_DISABLED` | 403 | Feature not on clinic's plan |
| `INVALID_PHONE` | 422 | Phone number not in E.164 format |
| `REPORT_UPLOAD_FAILED` | 500 | Storage upload failed |
| `WA_DELIVERY_FAILED` | 502 | WhatsApp API returned error |
| `UNAUTHORIZED` | 401 | Invalid/expired JWT |
| `CLINIC_NOT_FOUND` | 404 | Unknown clinic_id |

### Routes

```
# Auth
POST /auth/otp/send              → Send OTP to owner's WhatsApp/phone
POST /auth/otp/verify            → Verify OTP → return JWT

# Clinics
POST /api/v1/clinics             → Register new clinic
GET  /api/v1/clinics/{id}        → Get clinic details
PUT  /api/v1/clinics/{id}        → Update settings

# Appointments (all support ?page=&per_page=&from_date=&to_date=&status=)
GET    /api/v1/clinics/{id}/appointments              → List (paginated)
POST   /api/v1/clinics/{id}/appointments              → Create
PUT    /api/v1/clinics/{id}/appointments/{appt_id}    → Update status
DELETE /api/v1/clinics/{id}/appointments/{appt_id}    → Soft delete

# Test Bookings
GET    /api/v1/clinics/{id}/test-bookings                       → List (paginated)
POST   /api/v1/clinics/{id}/test-bookings                       → Create
PUT    /api/v1/clinics/{id}/test-bookings/{booking_id}          → Update
POST   /api/v1/clinics/{id}/test-bookings/{booking_id}/report   → Upload PDF → auto-deliver
DELETE /api/v1/clinics/{id}/test-bookings/{booking_id}          → Soft delete

# Report Ready Trigger (called by LIMS or manually)
POST /api/v1/report-ready
  Body: { clinic_id, patient_phone, test_name, report_pdf_url | report_pdf_base64 }
  → Uploads PDF, creates signed URL, sends WhatsApp document, schedules recall

# Patients
GET  /api/v1/clinics/{id}/patients                      → List (paginated, ?tag=)
GET  /api/v1/clinics/{id}/patients/{patient_id}         → Profile + full history
PUT  /api/v1/clinics/{id}/patients/{patient_id}         → Update (tags, notes)

# Test Catalog
GET    /api/v1/clinics/{id}/tests           → List (includes inactive if ?include_deleted=true)
POST   /api/v1/clinics/{id}/tests           → Add test
PUT    /api/v1/clinics/{id}/tests/{test_id} → Edit
DELETE /api/v1/clinics/{id}/tests/{test_id} → Soft delete

# Slots
GET    /api/v1/clinics/{id}/slots              → Available slots (?date=&doctor_id=)
POST   /api/v1/clinics/{id}/slots/bulk         → Generate slots for date range
DELETE /api/v1/clinics/{id}/slots/{slot_id}    → Block slot

# Reviews
GET  /api/v1/clinics/{id}/reviews             → List + draft replies
POST /api/v1/clinics/{id}/reviews/{id}/approve → Approve draft → auto-posts to GBP

# Broadcasts
POST /api/v1/clinics/{id}/broadcasts          → Create + send (checks plan feature flag)

# Stats
GET /api/v1/clinics/{id}/stats                → Dashboard summary (?from=&to=)

# Failed Messages (admin replay)
GET  /api/v1/clinics/{id}/failed-messages     → List unresolved
POST /api/v1/clinics/{id}/failed-messages/{id}/retry → Replay message through flow engine

# Health
GET /health                                   → { status: "ok", db: "ok", redis: "ok" }
```

### Report Ready Handler (key service)

```python
# app/api/reports.py

@router.post("/api/v1/report-ready")
async def report_ready(payload: ReportReadyPayload, db: AsyncSession):
    # 1. Find the test booking
    booking = await find_booking(db, payload.clinic_id,
                                 payload.patient_phone, payload.test_name)

    # 2. Upload PDF to storage
    if payload.report_pdf_url:
        stored_path = await storage.copy_from_url(payload.report_pdf_url)
    elif payload.report_pdf_base64:
        stored_path = await storage.upload_base64(payload.report_pdf_base64,
                                                  clinic_id=payload.clinic_id,
                                                  booking_id=str(booking.id))

    # 3. Generate signed URL (24-hour expiry for WhatsApp delivery)
    signed_url = await storage.get_signed_url(stored_path, expires_in=86400)

    # 4. Update booking status + audit log
    await update_booking_status(db, booking.id, "report_ready", stored_path)
    await write_audit(db, clinic_id=payload.clinic_id, action="report.delivered",
                      entity_type="test_booking", entity_id=booking.id)

    # 5. Send PDF on WhatsApp
    clinic = await get_clinic_cached(payload.clinic_id)  # cache-first
    filename = f"Report_{payload.test_name}_{today()}.pdf"
    await send_document(
        phone_number_id=clinic.settings["wa_phone_number_id"],
        to=payload.patient_phone,
        file_url=signed_url,
        filename=filename,
        caption=REPORT_DELIVERY_MSG.format(
            name=booking.patient.name, test=payload.test_name
        ),
        access_token=clinic.settings["wa_access_token"]
    )

    # 6. Schedule recall if applicable (HbA1c → 3 months, Annual checkup → 12 months)
    await maybe_create_recall(db, booking)

    return {"data": {"status": "delivered", "filename": filename}}
```

---

## 9. Caching Layer

Redis is provisioned from Day 1 — not just for future task queue use, but because three objects are read on every incoming message and must be cached.

### Cache Strategy

```python
# app/services/cache.py

import redis.asyncio as aioredis
import json

redis = aioredis.from_url(settings.REDIS_URL)

CACHE_TTL = {
    "clinic_by_phone_id": 3600,      # 1 hour — clinic config changes rarely
    "tests_catalog":       1800,      # 30 min
    "conversation_session": 1800,     # 30 min — matches DB session expiry
}

CACHE_KEYS = {
    "clinic":   "clinic:{phone_number_id}",
    "tests":    "tests:{clinic_id}",
    "session":  "session:{wa_number}:{clinic_id}",
}

async def get_clinic_cached(phone_number_id: str, db) -> dict:
    key = f"clinic:{phone_number_id}"
    cached = await redis.get(key)
    if cached:
        return json.loads(cached)
    clinic = await db_get_clinic_by_phone_id(db, phone_number_id)
    await redis.setex(key, CACHE_TTL["clinic_by_phone_id"], json.dumps(clinic))
    return clinic

async def get_tests_cached(clinic_id: str, db) -> list:
    key = f"tests:{clinic_id}"
    cached = await redis.get(key)
    if cached:
        return json.loads(cached)
    tests = await db_get_active_tests(db, clinic_id)
    await redis.setex(key, CACHE_TTL["tests_catalog"], json.dumps(tests))
    return tests

async def get_session_cached(wa_number: str, clinic_id: str, db) -> dict:
    key = f"session:{wa_number}:{clinic_id}"
    cached = await redis.get(key)
    if cached:
        return json.loads(cached)
    session = await db_get_session(db, wa_number, clinic_id)
    if session:
        await redis.setex(key, CACHE_TTL["conversation_session"], json.dumps(session))
    return session

async def invalidate_clinic_cache(phone_number_id: str):
    """Call this whenever clinic settings are updated."""
    await redis.delete(f"clinic:{phone_number_id}")

async def invalidate_tests_cache(clinic_id: str):
    """Call this whenever test catalog is modified."""
    await redis.delete(f"tests:{clinic_id}")

async def update_session_cache(wa_number: str, clinic_id: str, session: dict):
    """Write-through: update both DB and cache atomically."""
    key = f"session:{wa_number}:{clinic_id}"
    await redis.setex(key, CACHE_TTL["conversation_session"], json.dumps(session))
```

### Cache Invalidation Rules

| Event | Invalidate |
|---|---|
| `PUT /api/v1/clinics/{id}` (settings update) | `clinic:{phone_number_id}` |
| Any test created/edited/deleted | `tests:{clinic_id}` |
| Session expires (30 min) | Auto-expires via Redis TTL |
| Clinic plan changes | `clinic:{phone_number_id}` |

---

## 10. Scheduler & Automation Engine

```python
# app/scheduler.py

from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")

@scheduler.scheduled_job('interval', minutes=5, id='appointment_reminders')
async def send_appointment_reminders():
    async with get_db() as db:
        for appt in await get_appointments_due_reminder(db, hours_ahead=24):
            if not appt.reminder_24hr_sent:
                await send_template_reminder(appt, "24hr")
                await mark_reminder_sent(db, appt.id, "24hr")
        for appt in await get_appointments_due_reminder(db, hours_ahead=1):
            if not appt.reminder_1hr_sent:
                await send_template_reminder(appt, "1hr")
                await mark_reminder_sent(db, appt.id, "1hr")

@scheduler.scheduled_job('interval', minutes=15, id='review_requests')
async def send_review_requests():
    """2 hours after appointment time → review request."""
    async with get_db() as db:
        for appt in await get_appointments_for_review(db):
            await send_review_request_message(appt)
            await mark_review_request_sent(db, appt.id)

@scheduler.scheduled_job('interval', hours=1, id='recalls')
async def process_recalls():
    async with get_db() as db:
        for recall in await get_due_recalls(db):
            await send_recall_message(recall)
            await mark_recall_sent(db, recall.id)

@scheduler.scheduled_job('cron', hour=20, minute=0, id='fasting_reminders')
async def send_fasting_reminders():
    async with get_db() as db:
        for booking in await get_tomorrow_fasting_bookings(db):
            if not booking.fasting_reminder_sent:
                await send_fasting_reminder(booking)

@scheduler.scheduled_job('cron', hour=9, minute=0, id='daily_digest')
async def send_daily_digest():
    async with get_db() as db:
        for clinic in await get_active_clinics(db):
            stats = await get_yesterday_stats(db, clinic.id)
            await send_daily_digest_message(clinic, stats)

@scheduler.scheduled_job('interval', hours=6, id='no_show_marking')
async def mark_no_shows():
    async with get_db() as db:
        await update_no_shows(db)

@scheduler.scheduled_job('interval', hours=6, id='gbp_review_fetch')
async def fetch_gbp_reviews():
    """Fetch new GBP reviews, generate AI reply drafts, notify owners."""
    async with get_db() as db:
        for clinic in await get_gbp_enabled_clinics(db):
            await fetch_new_reviews(clinic.id, db)

# Scheduler health monitoring — log if job misses its window
@scheduler.scheduled_job('interval', minutes=10, id='scheduler_heartbeat')
async def scheduler_heartbeat():
    logger.info("scheduler.heartbeat", extra={"event": "scheduler.alive"})
```

---

## 11. Report PDF Delivery System

### Two Modes

**Mode A — Pass-Through (Recommended for MVP)**
Clinic's existing LIMS generates PDFs. Your system receives a webhook or API call and forwards to WhatsApp.

Integration options with LIMS:
- Direct webhook: LIMS calls `POST /api/v1/report-ready` with PDF URL
- Manual upload: staff uploads via web dashboard
- Email-to-webhook bridge: if LIMS emails reports, parse the email and trigger delivery

**Mode B — Generate PDF In-App**
Build your own report template (useful for centres without LIMS).

```python
# app/services/pdf_generator.py

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from io import BytesIO

def generate_report_pdf(patient_name: str, test_name: str,
                        results: list[dict], clinic_name: str,
                        clinic_logo_url: str = None) -> bytes:
    """
    results = [
        {"parameter": "Hemoglobin", "value": "13.5", "unit": "g/dL",
         "reference": "12–17", "flag": "normal"},
    ]
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    # Build story: clinic header, patient info, results table, footer
    doc.build(story)
    return buffer.getvalue()
```

### Password Protection (Optional)

```python
import pikepdf
from io import BytesIO

def password_protect_pdf(pdf_bytes: bytes, password: str) -> bytes:
    with pikepdf.open(BytesIO(pdf_bytes)) as pdf:
        output = BytesIO()
        pdf.save(output, encryption=pikepdf.Encryption(
            user=password, owner=password
        ))
        return output.getvalue()

# Password = patient's DOB in DDMMYYYY format
# Include in delivery message: "Password: aapki date of birth (DDMMYYYY)"
```

### Storage

```python
# app/services/storage.py

async def upload_report_pdf(pdf_bytes: bytes, clinic_id: str,
                            booking_id: str) -> str:
    key = f"reports/{clinic_id}/{booking_id}/report.pdf"
    await storage_client.upload(key, pdf_bytes,
                                content_type="application/pdf")
    return key

async def get_signed_url(path: str, expires_in: int = 86400) -> str:
    """24-hour signed URL for WhatsApp document delivery."""
    return await storage_client.create_signed_url(path, expires_in)
```

---

## 12. Google Business Profile (GBP) Autopilot

### Capabilities
1. Fetch new reviews every 6 hours
2. AI-generate Hindi/English reply drafts (Claude API)
3. Send draft to owner for WhatsApp approval
4. Post approved reply to Google
5. Post weekly health tip content to GBP

> Feature-gated: only active when `clinic.settings.features.gbp_autopilot = true`

### Setup
```
1. Enable "My Business Business Information API" and "My Business Reviews API"
   in Google Cloud Console
2. OAuth2 flow for each clinic via web dashboard
3. Store refresh_token in clinics.settings["gbp_refresh_token"]
```

```python
# app/services/gbp_service.py

async def fetch_new_reviews(clinic_id: str, db):
    clinic = await get_clinic_cached(clinic_id, db)
    if not clinic["settings"]["features"].get("gbp_autopilot"):
        return

    creds = build_credentials(clinic["settings"]["gbp_refresh_token"])
    service = build("mybusiness", "v4", credentials=creds)
    reviews = service.accounts().locations().reviews().list(
        parent=clinic["settings"]["gbp_location_name"]
    ).execute()

    for review in reviews.get("reviews", []):
        if not await review_exists(db, review["reviewId"]):
            await save_review(db, clinic_id, review)
            draft = await generate_review_reply(
                review_text=review.get("comment", ""),
                clinic_name=clinic["name"],
                rating=review.get("starRating")
            )
            await save_draft_reply(db, review["reviewId"], draft)
            await notify_owner_new_review(clinic, review, draft)

async def generate_review_reply(review_text, clinic_name, rating) -> str:
    """Call Claude API to generate contextual Hindi/English reply."""
    # Returns 2–3 sentence professional reply
    pass
```

---

## 13. Feature Flags

Feature flags are stored per-clinic in `clinics.settings.features` JSONB. This gates plan-restricted features at runtime without hardcoded plan checks scattered through code.

### Flag Schema

```json
{
  "features": {
    "gbp_autopilot":        false,
    "llm_intent_fallback":  true,
    "broadcasts":           false,
    "home_collection":      true,
    "multi_doctor":         false,
    "recall_automation":    true,
    "report_delivery":      true
  }
}
```

### Flags by Plan

| Feature | starter | clinic | diagnostic | chain |
|---|---|---|---|---|
| `report_delivery` | ❌ | ❌ | ✅ | ✅ |
| `home_collection` | ❌ | ❌ | ✅ | ✅ |
| `recall_automation` | ✅ | ✅ | ✅ | ✅ |
| `broadcasts` | ❌ | ✅ | ✅ | ✅ |
| `gbp_autopilot` | ❌ | ✅ | ✅ | ✅ |
| `multi_doctor` | ❌ | ✅ | ❌ | ✅ |
| `llm_intent_fallback` | ✅ | ✅ | ✅ | ✅ |

### Usage Pattern

```python
# app/services/feature_flags.py

async def require_feature(clinic_id: str, feature: str, db):
    """Raises PlanFeatureDisabled if feature is off for this clinic."""
    clinic = await get_clinic_cached(clinic_id, db)
    if not clinic["settings"]["features"].get(feature):
        raise PlanFeatureDisabledError(
            f"Feature '{feature}' is not available on your current plan."
        )

# Usage in any handler:
await require_feature(clinic_id, "broadcasts", db)
# → auto-returns HTTP 403 with standard error envelope if flag is off
```

### Flag Management
- Flags are set during onboarding based on chosen plan
- Flags are updated automatically on plan upgrade/downgrade
- Individual flags can be manually toggled in DB for beta testing or exceptions

---

## 14. Admin Dashboard (Minimal Web UI)

### Purpose
Not needed for daily operations (done via WhatsApp commands), but required for:
- Initial clinic onboarding and setup
- Uploading report PDFs manually
- Analytics and history
- Test catalog management
- Failed message replay

### Tech: React (Vite) + Tailwind CSS + REST API

### Pages

```
/login                  → Phone OTP login (no password)
/dashboard              → Today: appointments, tests, pending reports, reviews
/appointments           → Calendar + list, filter by date/doctor/status
/test-bookings          → All bookings, status filter, report upload button
/patients               → Patient list + search, individual profile with history
/tests                  → Test catalog (add, edit, toggle active)
/reports/upload         → PDF upload → auto-triggers WhatsApp delivery
/reports/pending        → Reports not yet delivered (action: upload)
/recalls                → Upcoming recall schedule + manual trigger
/reviews                → GBP review monitor + approve/edit reply
/broadcasts             → Draft + send bulk messages (plan-gated)
/settings               → Clinic info, hours, WhatsApp config, plan
/onboarding             → New clinic setup wizard
/failed-messages        → Failed message inbox + retry button
```

### Dashboard Stats Cards
```
Today's appointments:    14  (2 cancelled, 1 no-show)
Tests booked today:      28  (8 home collection, 20 walkin)
Reports delivered:       22  via WhatsApp
Pending report delivery:  6  (action required)
New reviews this week:    3  (avg 4.8 ⭐)
Recalls due this month:  47
Failed messages:          0  ✅
```

---

## 15. Onboarding Flow

### Option A — WhatsApp Onboarding (Zero Dashboard)
```
1. Owner messages "register" to your master onboarding WA number
2. Bot: clinic name, city, type (GP/diagnostic/dental)
3. Bot: their WhatsApp Business number to connect
4. Bot: working hours ("Monday-Saturday 9am-8pm?")
5. Diagnostic: bot sends Google Form link for test catalog CSV
6. OTP verification to clinic's WA number
7. Confirmation + quick-start guide
→ Features provisioned based on plan default
```

### Option B — Web Wizard (Better UX, Recommended)
```
Step 1: Basic info (name, type, city, owner phone)
Step 2: WhatsApp Business connection (Meta Embedded Signup)
Step 3: Working hours (visual week grid)
Step 4: Test catalog upload CSV (template provided) — diagnostic only
Step 5: Plan selection + Razorpay payment
→ Auto-provisions webhook, seeds feature flags, sends welcome WA message
```

---

## 16. Security, Compliance & Data Handling

### DPDP Act 2023 (India) — Consent

```python
# Consent MUST be captured at first interaction before any data is stored

CONSENT_MESSAGE = """Namaste! 🙏 {clinic_name} ke WhatsApp service mein swagat!

Yahan se appointments book karein, reports paayen, aur reminders lein.

📋 Iske liye hum aapka naam aur number save karenge.
Kya aap agree karte hain?

1️⃣ Haan, main agree karta/karti hoon
2️⃣ Nahi"""

# On consent:
#   patients.opt_in = TRUE, patients.opt_in_at = NOW()
#   audit_log entry: action='patient.consent_given'
# On decline:
#   Still allow one-time queries, never add to recall/broadcast lists
#   audit_log entry: action='patient.consent_declined'
```

### Data Handling Rules

| Data Type | Storage | Retention | Access |
|---|---|---|---|
| Patient name + phone | Postgres (encrypted at rest) | Indefinite (soft delete only) | clinic_id scoped |
| Conversation sessions | Postgres + Redis | 30-min session, 90-day log | clinic_id scoped |
| Report PDFs | S3/Supabase (private bucket) | 2 years minimum | Signed URL, 24-hr expiry |
| Audit log | Postgres | 7 years (DPDP) | System/admin only |
| WA message content | Postgres messages table | 90 days then purge | clinic_id scoped |
| PHI in bot context | Redis session only | Expires with session | Never persisted long-term |

### Security Controls

```python
# 1. JWT Authentication
#    Payload: { clinic_id, role: "owner"|"staff", exp, jti }
#    Short expiry: 1 hour access token + 7-day refresh token

# 2. Multi-tenant query enforcement
#    ALL queries include clinic_id filter
#    RLS policies provide second layer (see Section 5)
#    Set session variable before each request:
await db.execute("SET app.clinic_id = :id", {"id": clinic_id})

# 3. PII masking in logs
def mask_phone(number: str) -> str:
    return f"****{number[-4:]}"

# 4. Rate limiting
#    Webhook endpoint: 100 req/min per phone_number_id
#    API endpoints: 1000 req/min per JWT clinic_id

# 5. Secrets — never in code
#    All sensitive values in environment variables
#    Per-clinic WA tokens stored in clinics.settings (encrypted column in prod)
#    Rotation: document process for rotating WA access tokens on compromise

# 6. HTTPS enforced
#    WhatsApp webhook requires HTTPS — TLS from Day 1
#    HSTS header on all responses
```

---

## 17. Observability & Alerting

### Structured Log Schema

Every log entry must be structured JSON with these fields:

```python
# app/utils/logger.py

import structlog

logger = structlog.get_logger()

# Usage:
logger.info("flow.step.transition",
    clinic_id=clinic_id,
    patient_wa=mask_phone(wa_number),   # PII-safe: last 4 digits only
    flow="test_booking",
    step="SELECT_SLOT",
    wa_message_id="wamid.xxx",
    duration_ms=45,
    event="flow.step.transition"
)

# All log events follow this schema:
{
  "timestamp":       "2026-05-15T14:32:11.123Z",
  "level":           "INFO",
  "clinic_id":       "uuid",
  "patient_wa":      "****3210",     # last 4 only
  "flow":            "test_booking",
  "step":            "SELECT_SLOT",
  "wa_message_id":   "wamid.xxx",
  "duration_ms":     45,
  "event":           "flow.step.transition",
  "request_id":      "uuid"
}
```

### Mandatory Alert Rules

| Condition | Threshold | Action |
|---|---|---|
| Webhook response time | > 3 seconds | Alert on-call |
| WhatsApp delivery failed status | Any occurrence | Write to failed_messages + alert owner |
| Scheduler job missed | 2× scheduled interval with no run | Alert on-call |
| Failed messages count | > 10 unresolved | Alert on-call |
| Report delivery failure | Any occurrence | Alert clinic owner via WA |
| DB connection pool exhausted | > 80% utilization | Alert on-call |

### Health Check Endpoint

```python
@app.get("/health")
async def health_check(db: AsyncSession, redis: Redis):
    db_ok = await check_db(db)
    redis_ok = await check_redis(redis)
    scheduler_ok = scheduler.running
    return {
        "status": "ok" if all([db_ok, redis_ok, scheduler_ok]) else "degraded",
        "db": "ok" if db_ok else "error",
        "redis": "ok" if redis_ok else "error",
        "scheduler": "ok" if scheduler_ok else "stopped"
    }
```

---

## 18. Environment Variables & Config

```bash
# .env — never commit to version control

# App
APP_ENV=production
SECRET_KEY=<32-char random string>
BASE_URL=https://yourdomain.com
ALLOWED_HOSTS=yourdomain.com

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/clinic_db

# Redis
REDIS_URL=redis://localhost:6379/0

# WhatsApp Cloud API
WA_APP_ID=<meta_app_id>
WA_APP_SECRET=<meta_app_secret>
WA_VERIFY_TOKEN=<your_webhook_verify_token>
# Per-clinic tokens stored in clinics.settings JSONB, not here

# Anthropic Claude
ANTHROPIC_API_KEY=sk-ant-...

# Storage
STORAGE_PROVIDER=supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=<service_role_key>
SUPABASE_STORAGE_BUCKET=clinic-reports
# OR for S3:
# AWS_ACCESS_KEY_ID=...
# AWS_SECRET_ACCESS_KEY=...
# S3_BUCKET_NAME=clinic-reports
# S3_REGION=ap-south-1

# Payments
RAZORPAY_KEY_ID=rzp_live_...
RAZORPAY_KEY_SECRET=...

# Google (GBP)
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=https://yourdomain.com/auth/google/callback

# Email alerts (internal)
SMTP_HOST=smtp.postmarkapp.com
SMTP_PORT=587
SMTP_USER=...
SMTP_PASS=...
ALERT_EMAIL=your@email.com

# Monitoring
SENTRY_DSN=https://xxx@sentry.io/xxx
LOG_LEVEL=INFO
```

### Secret Rotation Procedure
```
WhatsApp Access Tokens:
  - Tokens are long-lived but can be regenerated in Meta Business Manager
  - On rotation: UPDATE clinics SET settings = jsonb_set(settings, '{wa_access_token}', '"new_token"')
    WHERE id = '<clinic_id>'
  - Then: invalidate Redis cache for that clinic

Database Password:
  - Update DATABASE_URL in env
  - Redeploy app (zero-downtime with rolling restart)

Anthropic API Key:
  - Regenerate in Anthropic console
  - Update ANTHROPIC_API_KEY in env
  - Redeploy
```

---

## 19. Deployment — Options & Recommendation

### MVP Deployment: Railway.app

```toml
# railway.toml
[build]
builder = "NIXPACKS"

[deploy]
startCommand = "uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2"
healthcheckPath = "/health"
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
```

Railway services to provision:
1. FastAPI web service (auto-deploy from GitHub main branch)
2. PostgreSQL (Railway managed — automatic backups)
3. Redis (Railway managed)
4. React dashboard via Vercel (separate, free tier)

**Cost estimate: ~$10–20/month**

### Production Deployment: Docker Compose on Hetzner

```yaml
# docker-compose.yml

version: '3.8'
services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
      target: production         # multi-stage build
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

  worker:
    build:
      context: .
      target: production
    command: celery -A app.worker worker --loglevel=info --concurrency=4
    env_file: .env
    depends_on:
      - db
      - redis
    restart: unless-stopped

  scheduler:
    build:
      context: .
      target: production
    command: celery -A app.worker beat --loglevel=info
    env_file: .env
    depends_on:
      - redis
    restart: unless-stopped

  db:
    image: postgres:16-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: clinic_db
      POSTGRES_USER: clinic_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U clinic_user -d clinic_db"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf
      - certbot_certs:/etc/letsencrypt
    depends_on:
      - api
    restart: unless-stopped

volumes:
  postgres_data:
  certbot_certs:
```

### Multi-Stage Dockerfile

```dockerfile
# Dockerfile

FROM python:3.11-slim AS base
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM base AS development
COPY . .
CMD ["uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS production
COPY . .
RUN useradd -m -u 1000 appuser && chown -R appuser /app
USER appuser
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

**Recommended VPS: Hetzner CX21** — 2 vCPU, 4GB RAM, €5.77/month ≈ ₹540/month

**Domain:** Namecheap (~₹800/year) | **SSL:** Let's Encrypt via Certbot (free, auto-renew)

---

## 20. MVP Scope for Pilot (Diagnostic Centre)

### 6-Week Build Plan

#### Week 1–2: Core Infrastructure
- [ ] FastAPI project with SQLAlchemy 2.0 async + Alembic
- [ ] Complete PostgreSQL schema (all tables, triggers, indexes, RLS)
- [ ] Redis connection + session/clinic/test caching layer
- [ ] WhatsApp Cloud API webhook handler (signature verify, idempotency, dead-letter)
- [ ] Message sender utilities (text, list, buttons, document, template)
- [ ] Pydantic validation for all incoming WA payloads
- [ ] Conversation session state machine base
- [ ] Single clinic seeded (pilot diagnostic centre config)
- [ ] Railway deployment + health endpoint live

#### Week 3–4: Diagnostic Centre Core Flows
- [ ] Test catalog seeded (12 common tests)
- [ ] Test booking flow: category → test → walkin/home → slot → confirm → payment
- [ ] Home collection flow: address/location capture → technician slot
- [ ] Consent/opt-in capture on first message
- [ ] Report ready endpoint: PDF upload → signed URL → WhatsApp document delivery
- [ ] Fasting reminder (night before fasting tests, 8 PM cron)
- [ ] Password-protected PDF option

#### Week 5–6: Automation + Admin
- [ ] APScheduler setup and all 6 jobs running
- [ ] Appointment/booking reminders (24hr + 1hr)
- [ ] Post-booking review request (2 hours after appointment)
- [ ] Recall scheduling after report delivery (HbA1c → 3 months, etc.)
- [ ] Doctor admin WhatsApp commands: view today, send report, daily stats
- [ ] Daily digest message to owner (9 AM)
- [ ] Minimal web dashboard: bookings list, pending reports, PDF upload button
- [ ] Failed message inbox + retry in dashboard
- [ ] Audit log writing for all key events

### Pilot Seed Data

```python
# scripts/seed_pilot.py

CLINIC = {
    "name": "<Uncle's Lab Name>",
    "clinic_type": "diagnostic",
    "whatsapp_number": "+91XXXXXXXXXX",    # lab's WA business number
    "owner_whatsapp": "+91XXXXXXXXXX",     # uncle's personal WA for admin commands
    "city": "Bhopal",
    "settings": {
        "home_collection": True,
        "home_collection_slots": ["06:00","06:30","07:00","07:30","08:00"],
        "walkin_hours": "8 AM – 8 PM",
        "report_delivery_hours": 4,
        "language": "hinglish",
        "features": {
            "gbp_autopilot": False,          # enable after pilot
            "llm_intent_fallback": True,
            "broadcasts": False,
            "home_collection": True,
            "multi_doctor": False,
            "recall_automation": True,
            "report_delivery": True
        }
    }
}

TESTS = [
    {"name": "CBC (Complete Blood Count)",              "price": 250,  "fasting": False, "category": "general",  "duration_hours": 4},
    {"name": "Lipid Profile",                           "price": 450,  "fasting": True,  "category": "cardiac",  "duration_hours": 6},
    {"name": "HbA1c",                                   "price": 350,  "fasting": False, "category": "diabetes", "duration_hours": 4},
    {"name": "Fasting Blood Sugar",                     "price":  80,  "fasting": True,  "category": "diabetes", "duration_hours": 2},
    {"name": "Diabetes Package (HbA1c + FBS + PPBS)",   "price": 550,  "fasting": True,  "category": "diabetes", "duration_hours": 6},
    {"name": "Thyroid Profile (T3/T4/TSH)",             "price": 400,  "fasting": False, "category": "thyroid",  "duration_hours": 6},
    {"name": "Liver Function Test (LFT)",               "price": 500,  "fasting": True,  "category": "liver",    "duration_hours": 6},
    {"name": "Kidney Function Test (KFT/RFT)",          "price": 450,  "fasting": False, "category": "kidney",   "duration_hours": 6},
    {"name": "Full Body Checkup",                       "price": 1499, "fasting": True,  "category": "package",  "duration_hours": 8},
    {"name": "Urine Routine",                           "price":  80,  "fasting": False, "category": "general",  "duration_hours": 2},
    {"name": "Vitamin D3",                              "price": 600,  "fasting": False, "category": "vitamins", "duration_hours": 24},
    {"name": "Vitamin B12",                             "price": 500,  "fasting": False, "category": "vitamins", "duration_hours": 24},
]
```

### Pilot Success Metrics (60-Day Free Trial)
- Inbound phone calls for test booking: target down 50%+
- Report delivery time: same-day WhatsApp vs prior method
- Patient opt-in rate on first contact: target 80%+
- Home collection no-show rate: below 10%
- Uncle's verdict: would pay ₹1,499/month → Y/N

---

## 21. File & Folder Structure

```
clinic-whatsapp-suite/
├── INVARIANTS.md                       # Project constraints for AI coding assistants
├── app/
│   ├── main.py                     # FastAPI app init, middleware, router mount
│   ├── config.py                   # Pydantic BaseSettings (reads from .env)
│   ├── database.py                 # SQLAlchemy async engine + session factory
│   ├── dependencies.py             # FastAPI Depends: get_db, get_redis, get_current_clinic
│   │
│   ├── models/                     # SQLAlchemy ORM models
│   │   ├── base.py                 # TimestampMixin, SoftDeleteMixin
│   │   ├── clinic.py
│   │   ├── patient.py
│   │   ├── appointment.py
│   │   ├── test_booking.py
│   │   ├── test.py
│   │   ├── conversation.py
│   │   ├── message.py
│   │   ├── failed_message.py
│   │   ├── audit_log.py
│   │   ├── recall_schedule.py
│   │   └── review.py
│   │
│   ├── schemas/                    # Pydantic schemas (request + response)
│   │   ├── whatsapp_webhook.py     # Validated WA payload shapes
│   │   ├── clinic.py
│   │   ├── appointment.py
│   │   ├── test_booking.py
│   │   ├── patient.py
│   │   ├── report.py
│   │   └── common.py              # Paginated response + error envelope
│   │
│   ├── api/                        # REST route handlers
│   │   ├── auth.py
│   │   ├── clinics.py
│   │   ├── appointments.py
│   │   ├── test_bookings.py
│   │   ├── reports.py
│   │   ├── patients.py
│   │   ├── tests.py
│   │   ├── slots.py
│   │   ├── reviews.py
│   │   ├── broadcasts.py
│   │   ├── stats.py
│   │   └── failed_messages.py
│   │
│   ├── webhooks/
│   │   └── whatsapp.py             # Incoming WA webhook: verify + dispatch
│   │
│   ├── services/
│   │   ├── whatsapp_sender.py      # All WA send functions
│   │   ├── intent_router.py        # Classify intent (rule-based + LLM fallback)
│   │   ├── flow_engine.py          # Session state machine dispatcher
│   │   ├── cache.py                # Redis get/set/invalidate helpers
│   │   ├── storage.py              # PDF upload/signed URL
│   │   ├── gbp_service.py          # Google Business Profile
│   │   ├── llm_service.py          # Claude API calls
│   │   ├── feature_flags.py        # require_feature() helper
│   │   └── audit.py                # write_audit() helper
│   │
│   ├── flows/                      # Individual conversation flows
│   │   ├── base_flow.py            # Abstract base: handle(session, message)
│   │   ├── test_booking_flow.py
│   │   ├── appointment_flow.py
│   │   ├── report_inquiry_flow.py
│   │   ├── admin_flow.py
│   │   ├── onboarding_flow.py
│   │   ├── recall_flow.py
│   │   └── consent_flow.py         # First-time opt-in
│   │
│   ├── scheduler.py                # APScheduler job definitions
│   │
│   ├── templates/                  # Message string templates
│   │   ├── hinglish.py             # Default
│   │   ├── hindi.py
│   │   └── english.py
│   │
│   └── utils/
│       ├── phone.py                # Normalize to E.164, mask for logs
│       ├── datetime_utils.py       # IST timezone, slot generation
│       └── pdf_utils.py            # Generate + password protect PDFs
│
├── migrations/                     # Alembic
│   ├── env.py
│   └── versions/
│
├── dashboard/                      # React (Vite) frontend
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   └── api/                    # Typed API client
│   └── package.json
│
├── scripts/
│   ├── seed_pilot.py
│   ├── seed_tests.py
│   └── register_meta_templates.py  # Submit WA templates via API
│
├── tests/
│   ├── conftest.py                 # Fixtures: test DB, mock WA sender
│   ├── test_flows/
│   │   ├── test_test_booking.py
│   │   ├── test_appointment.py
│   │   └── test_admin_commands.py
│   ├── test_api/
│   │   ├── test_report_ready.py
│   │   └── test_appointments_api.py
│   ├── test_webhook/
│   │   ├── test_idempotency.py
│   │   └── test_signature_verify.py
│   └── test_scheduler/
│       └── test_reminder_jobs.py
│
├── docker-compose.yml
├── docker-compose.dev.yml          # Dev override: reload, no workers
├── Dockerfile
├── requirements.txt
├── .env.example
├── railway.toml
└── README.md
```

---

## 22. Third-Party Services

| Service | Purpose | Cost | Setup Difficulty |
|---|---|---|---|
| **Meta WhatsApp Cloud API** | WhatsApp messaging | Free (1000 conv/mo), then ~₹0.40–0.60/conversation | Medium — needs Meta Business verification |
| **Supabase** | Postgres + Storage + Auth | Free tier for MVP | Easy |
| **Anthropic Claude API** | Intent classification, review replies | ~$0.01/1000 msgs (Haiku model) | Easy |
| **Redis** | Caching + future task queue | Included in Railway/Hetzner stack | Easy |
| **Google Cloud (My Business API)** | GBP review monitoring | Free API | Medium — OAuth2 setup |
| **Razorpay** | Subscription billing | 2% transaction fee | Easy |
| **Railway.app or Hetzner** | Hosting | ₹400–1500/month | Easy |
| **Postmark / Resend** | Internal alert emails | Free tier | Easy |
| **Namecheap** | Domain | ₹800/year | Easy |

### Meta WhatsApp Cloud API — Account Requirements
1. Meta Business Manager (government ID verified — takes 1–3 days)
2. WhatsApp Business Account (WABA) under Business Manager
3. Display name approval from Meta (2–3 business days)
4. Phone number — any number not on personal WhatsApp; can migrate existing WA Business numbers
5. App in Live mode (not Development) before messaging real patients

---

## 23. Testing Strategy

### Unit Tests — Flow Logic

```python
# tests/test_flows/test_test_booking.py

@pytest.mark.asyncio
async def test_booking_start_shows_categories():
    session = make_session(flow=None, step=None)
    response = await test_booking_flow.handle(session, message_text("blood test"), db=mock_db)
    assert "CBC" in response or any(test in response for test in ["Lipid", "Thyroid", "Diabetes"])

@pytest.mark.asyncio
async def test_home_collection_asks_for_address():
    session = make_session(flow="test_booking", step="SELECT_TYPE",
                           context={"selected_test_id": "uuid", "selected_test_name": "HbA1c"})
    response = await test_booking_flow.handle(session, button_reply("home"), db=mock_db)
    assert "address" in response.lower() or "location" in response.lower()

@pytest.mark.asyncio
async def test_fasting_test_schedules_reminder():
    booking = make_booking(test_name="Diabetes Package", requires_fasting=True,
                           collection_slot=tomorrow_6am())
    await maybe_send_fasting_reminder(booking)
    mock_wa_sender.send_template.assert_called_once_with(
        template_name="fasting_reminder", ...
    )
```

### Contract Tests — Webhook

```python
# tests/test_webhook/test_idempotency.py

@pytest.mark.asyncio
async def test_duplicate_message_is_silently_ignored():
    payload = sample_wa_text_message(wa_message_id="wamid.TEST123")
    # First call processes normally
    response1 = await client.post("/webhook/whatsapp", json=payload,
                                  headers=valid_signature_headers(payload))
    assert response1.status_code == 200
    # Second call with same wa_message_id must not re-process
    flow_engine_mock.reset_mock()
    response2 = await client.post("/webhook/whatsapp", json=payload,
                                  headers=valid_signature_headers(payload))
    assert response2.status_code == 200
    flow_engine_mock.handle.assert_not_called()

@pytest.mark.asyncio
async def test_invalid_signature_returns_403():
    payload = sample_wa_text_message()
    response = await client.post("/webhook/whatsapp", json=payload,
                                 headers={"X-Hub-Signature-256": "sha256=invalid"})
    assert response.status_code == 403
```

### API Contract Tests

```python
# tests/test_api/test_report_ready.py

@pytest.mark.asyncio
async def test_report_ready_delivers_pdf_and_creates_recall():
    with patch("app.services.whatsapp_sender.send_document") as mock_send:
        response = await client.post("/api/v1/report-ready", json={
            "clinic_id": TEST_CLINIC_ID,
            "patient_phone": "+919876543210",
            "test_name": "HbA1c",
            "report_pdf_url": "https://example.com/report.pdf"
        }, headers=auth_headers())
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "delivered"
        mock_send.assert_called_once()
    # Recall should be created for HbA1c (3-month follow-up)
    recalls = await get_patient_recalls(db, "+919876543210")
    assert any(r.trigger_type == "hba1c_quarterly" for r in recalls)

@pytest.mark.asyncio
async def test_error_response_matches_envelope():
    response = await client.post("/api/v1/report-ready", json={
        "clinic_id": "nonexistent-id",
        "patient_phone": "+919876543210",
        "test_name": "HbA1c"
    }, headers=auth_headers())
    assert response.status_code == 404
    body = response.json()
    assert "error" in body
    assert "code" in body["error"]
    assert "message" in body["error"]
    assert "request_id" in body["error"]
```

### Load Test Target

Use Locust to simulate 100 concurrent incoming WhatsApp messages. Target: webhook responds < 500ms p95.

---

## 24. INVARIANTS.md — Project Onboarding File

Create this file at the project root before writing a single line of code. Agent reads it automatically at session start.

```markdown
# INVARIANTS.md — WhatsApp Clinic Suite

## What This Is
WhatsApp-first SaaS for Indian clinics and diagnostic labs.
FastAPI + PostgreSQL + Redis. Multi-tenant. No mobile app.
Patients and doctors interact entirely through WhatsApp.

## Architecture Constraints — NEVER VIOLATE
1. Every DB query MUST include a clinic_id filter (multi-tenant safety)
2. Never hard-delete patient or appointment data — soft delete only (deleted_at)
3. Incoming webhook messages MUST be idempotency-checked (wa_message_id)
   before any processing begins
4. Write message to audit log BEFORE processing (write-first pattern)
5. All API errors MUST use the standard error envelope:
   { "error": { "code": "...", "message": "...", "details": {}, "request_id": "..." } }
6. PII in logs: patient phone numbers masked to last 4 digits only
7. Feature flags in clinic.settings.features MUST be checked before executing
   plan-gated features — use require_feature() helper
8. Row-Level Security: SET app.clinic_id before every DB transaction

## Key Files
- app/models/base.py     — TimestampMixin, SoftDeleteMixin (use on ALL mutable models)
- app/services/cache.py  — ALL clinic config, session, test catalog reads go through cache
- app/services/feature_flags.py — require_feature() for plan-gated features
- app/services/audit.py  — write_audit() for all state-changing operations
- app/schemas/common.py  — PaginatedResponse + ErrorEnvelope (use on all endpoints)

## Conversation Flow Rules
- Session state lives in conversation_sessions table + Redis cache
- Session expires after 30 minutes of inactivity
- Unknown intent → write to failed_messages, do NOT crash
- First message from any patient → run consent_flow BEFORE any other flow

## Scheduler Jobs (app/scheduler.py)
- appointment_reminders: every 5 min
- review_requests: every 15 min
- recalls: every hour
- fasting_reminders: daily 8 PM IST
- daily_digest: daily 9 AM IST
- no_show_marking: every 6 hours
- gbp_review_fetch: every 6 hours (feature-flagged)

## Test Patterns
- All flow tests use make_session() fixture from tests/conftest.py
- Mock WA sender in all tests — never call real Meta API
- Every new API endpoint needs: success case + error envelope shape test
- Idempotency tests required for any webhook handler changes

## NFRs to Keep in Mind
- Webhook ACK: < 500ms
- End-to-end message: < 2s
- Uptime: 99.5% monthly
- Never lose a message — failed_messages table is the safety net
```

---

## 25. Launch Checklist

### Technical
- [ ] Meta Business Manager verified (allow 1–3 days)
- [ ] WhatsApp number connected, display name approved (allow 2–3 days)
- [ ] All 7 message templates submitted and approved by Meta
- [ ] App switched to Live mode in Meta dashboard
- [ ] HTTPS with valid Let's Encrypt SSL cert
- [ ] Webhook URL registered and verified in Meta dashboard
- [ ] Alembic migrations run on production DB
- [ ] Pilot clinic seeded (test catalog + clinic config)
- [ ] Redis running and cache confirmed working (check logs)
- [ ] APScheduler confirmed running (heartbeat log visible)
- [ ] Round-trip test: send message to clinic WA → bot responds correctly
- [ ] Report delivery test: upload PDF → confirm patient receives on WA
- [ ] Idempotency test: send same message twice → confirm single processing
- [ ] Failed message test: intentionally break flow → confirm dead-letter entry
- [ ] RLS test: confirm query from clinic A cannot return clinic B data
- [ ] Sentry/Logfire connected and receiving events
- [ ] All 3 alerting rules configured (webhook latency, delivery failure, missed job)
- [ ] Health endpoint returning green (`/health`)

### Operational
- [ ] Uncle/owner walked through WhatsApp admin commands
- [ ] Uncle has web dashboard access (report upload + pending reports page)
- [ ] Consent message tested on uncle's number as patient
- [ ] Home collection technician briefed on ETA confirmation flow
- [ ] Backup plan documented: if bot goes down → staff use manual WA Business
- [ ] Owner alert number set in clinic config for urgent escalations
- [ ] `.env.example` matches all vars in `.env` (no missing undocumented vars)

### Go-Live
- [ ] Start with 5–10 regular patients: "Aab WhatsApp pe test book kar sakte hain"
- [ ] Monitor first 48 hours — watch failed_messages, scheduler logs, WA delivery status
- [ ] Daily check-in with uncle for first week
- [ ] Track baseline metrics: calls received, report delivery time, no-show rate
- [ ] Week 2: gather patient feedback on flow clarity (Hinglish tone, menu options)
- [ ] Week 4: share pilot results → go/no-go for 5-clinic expansion

---

*Build spec v2.0 | May 2026*
*Pilot target: 1 diagnostic centre, Bhopal | Expand to 5 clinics post-pilot*
*Stack: FastAPI · PostgreSQL · Redis · WhatsApp Cloud API · Claude API*
