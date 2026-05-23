# INVARIANTS.md — WhatsApp Clinic Suite
### Coding Rules & Guardrails | Enforced on every task

---

## ARCHITECTURE CONSTRAINTS — NEVER VIOLATE

These are not suggestions. Violating these introduces bugs that are invisible at write-time and catastrophic at runtime.

### 1. Multi-Tenancy — clinic_id on everything
Every query that touches `patients`, `appointments`, `test_bookings`, `conversation_sessions`, `messages`, or any patient-related table **must** filter by `clinic_id`. No exceptions.

```python
# ✅ Correct
await db.execute(select(Patient).where(
    Patient.clinic_id == clinic_id,
    Patient.whatsapp_number == phone
))

# ❌ Wrong — never query patients without clinic_id
await db.execute(select(Patient).where(Patient.whatsapp_number == phone))
```

Also set RLS session variable at the start of every request:
```python
await db.execute(text("SET app.clinic_id = :id"), {"id": str(clinic_id)})
```

### 2. Soft Delete — never hard delete patient data
Use `deleted_at = NOW()` and `deleted_by = actor_id`. Never run `DELETE FROM` on patient, appointment, or test_booking rows.

```python
# ✅ Correct
obj.deleted_at = datetime.utcnow()
obj.deleted_by = acting_user_id
await db.commit()

# ❌ Wrong
await db.delete(obj)
await db.commit()
```

All queries must exclude soft-deleted rows unless explicitly fetching history:
```python
# Add to all standard queries
.where(Patient.deleted_at.is_(None))
```

### 3. Webhook Write-First Pattern
In the WhatsApp webhook handler, the inbound message is logged to the `messages` table **before** any flow processing runs. If flow processing fails, the message still exists in DB and can be replayed from `failed_messages`.

```python
# ✅ Correct order
await log_inbound_message(db, ...)     # Step 1: write to DB
await flow_engine.handle(...)          # Step 2: process

# ❌ Wrong order
await flow_engine.handle(...)          # Don't process before logging
await log_inbound_message(db, ...)
```

### 4. Idempotency Check Before Processing
Every incoming WhatsApp message has a `wa_message_id`. Check it against `messages.wa_message_id` before touching any flow logic. Meta retries delivery — duplicate processing = duplicate bookings.

```python
if await message_already_processed(db, wa_message_id):
    return {"status": "ok"}   # Silent ACK, no further processing
```

### 5. Dead-Letter on Exception
If the flow engine raises any exception, write to `failed_messages` and return HTTP 200 to Meta (so it stops retrying). Never let an exception bubble up to a 500 response from the webhook endpoint.

```python
try:
    await flow_engine.handle(...)
except Exception as e:
    await write_failed_message(db, clinic_id, wa_number, wa_message_id, payload, str(e))
    # Do NOT re-raise — return 200 to Meta
```

### 6. Error Envelope on All API Endpoints
Every error response from any `/api/v1/` endpoint uses this exact shape:
```python
{
    "error": {
        "code": "SNAKE_CASE_CODE",
        "message": "Human readable message",
        "details": {},          # field-level errors if applicable
        "request_id": "uuid"    # always include for log correlation
    }
}
```

Use the `ErrorEnvelope` Pydantic schema from `app/schemas/common.py`. Do not return raw strings or custom shapes.

### 7. Feature Flags Before Plan-Gated Features
Before executing any feature that is plan-restricted, call `require_feature()`:

```python
from app.services.feature_flags import require_feature

# In any handler that uses a plan-gated feature:
await require_feature(clinic_id, "broadcasts", db)
await require_feature(clinic_id, "gbp_autopilot", db)
await require_feature(clinic_id, "home_collection", db)
```

This raises `HTTP 403` with error envelope automatically. Do not inline plan checks.

### 8. Cache-First for Clinic Config, Tests, and Sessions
Never read clinic config, test catalog, or conversation sessions directly from DB in the hot path (webhook handler, flow engine). Always go through the cache layer:

```python
from app.services.cache import get_clinic_cached, get_tests_cached, get_session_cached

clinic = await get_clinic_cached(phone_number_id, db)
tests  = await get_tests_cached(clinic_id, db)
session = await get_session_cached(wa_number, clinic_id, db)
```

After any clinic settings update, invalidate:
```python
await invalidate_clinic_cache(phone_number_id)
```

### 9. Audit Log on State Changes
Every action that changes state for a patient or clinic writes to `audit_log`:

```python
from app.services.audit import write_audit

await write_audit(
    db=db,
    clinic_id=clinic_id,
    actor_type="system",         # or "owner" / "patient"
    action="appointment.created",
    entity_type="appointment",
    entity_id=appointment.id,
    diff={"before": None, "after": appointment_dict}
)
```

Required for: appointment create/cancel, test booking create/cancel, report delivered, patient opt-in/opt-out, plan changes.

### 10. PII in Logs — Last 4 Digits Only
Patient phone numbers must never appear in full in any log output.

```python
from app.utils.phone import mask_phone

logger.info("flow.step", patient_wa=mask_phone(wa_number))
# Outputs: ****3210, never the full number
```

---

## CODE STYLE RULES

### Python
- Type hints on every function signature. No bare `Any` types without a comment explaining why.
- Async all the way down. No `def` in the request/response path — always `async def`.
- SQLAlchemy: always use `AsyncSession`, never `Session`. Always `await session.execute(select(...))`.
- Pydantic v2 syntax (`model_config = ConfigDict(...)` not `class Config`).
- Import order: stdlib → third-party → internal app imports. One blank line between groups.
- Max function length: 40 lines. If longer, split into helpers.
- No hardcoded strings in flow logic — all user-visible text goes in `app/templates/hinglish.py`.

### Naming
- DB models: `PascalCase` (e.g., `TestBooking`)
- Pydantic schemas: `PascalCase` with suffix `Schema`, `Request`, or `Response` (e.g., `TestBookingCreateRequest`)
- Service functions: `snake_case` verbs (e.g., `get_clinic_cached`, `write_failed_message`)
- Cache keys: defined as constants in `app/services/cache.py`, never inlined elsewhere
- Route paths: kebab-case (e.g., `/test-bookings`, `/failed-messages`)
- DB columns: `snake_case`

### SQLAlchemy Models
- All mutable models inherit `SoftDeleteMixin` (which inherits `TimestampMixin`)
- Immutable/log tables inherit `TimestampMixin` only (no soft delete needed)
- Every foreign key has an explicit `ondelete` strategy
- Every model has `__tablename__` defined

```python
# ✅ Correct model structure
class TestBooking(SoftDeleteMixin, Base):
    __tablename__ = "test_bookings"

    clinic_id   = Column(UUID(as_uuid=True), ForeignKey("clinics.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id  = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    status      = Column(String, nullable=False, default="booked")
    # ... all fields ...

    clinic  = relationship("Clinic", back_populates="test_bookings", lazy="selectin")
    patient = relationship("Patient", lazy="selectin")
```

### Pydantic Schemas
- Request schemas validate all incoming data strictly (`model_config = ConfigDict(extra="forbid")`)
- Response schemas never expose internal fields (no raw DB IDs for unrelated entities, no access tokens)
- WhatsApp webhook payload schemas use validators for unsupported message types

---

## TESTING RULES

### Before writing implementation code
1. Check if a test file already exists for that module
2. If not, create `tests/test_<module>/test_<feature>.py` first
3. Write the failing test(s) — happy path + at least two edge cases
4. Run the test suite, confirm it fails for the right reason
5. Then write implementation

### Test structure
```python
# Use pytest-asyncio for all async tests
# Use fixtures from tests/conftest.py — never create new DB connections in test files

@pytest.mark.asyncio
async def test_<feature>_<scenario>(db_session, mock_wa_sender):
    # Arrange
    ...
    # Act
    result = await the_function_under_test(...)
    # Assert
    assert result.something == expected
    mock_wa_sender.send_text.assert_called_once_with(...)
```

### What must always be mocked
- `app.services.whatsapp_sender` — never hit real Meta API in tests
- `app.services.storage` — never hit real Supabase/S3 in tests
- `app.services.llm_service` — never hit the real LLM provider API in tests
- External HTTP calls — use `httpx.MockTransport` or `respx`

### What must never be mocked
- Database operations — tests run against a real test DB (separate schema)
- Redis operations — tests run against a real Redis test instance

### Required test coverage
- Every new API endpoint: test success response shape + error envelope shape
- Every new flow step: test state transition + correct message sent
- Every webhook change: test idempotency + signature rejection

---

## WORKFLOW RULES

### Starting a task
Always read AGENTS.md first. Then confirm:
1. What file am I editing?
2. What does the failing test expect?
3. Does this touch any of the 10 architecture constraints above?

### Finishing a task
1. All new tests pass
2. No existing tests broken (run full suite: `pytest`)
3. Type check passes: `mypy app/`
4. Lint passes: `ruff check app/`
5. Update AGENTS.md: mark task complete, add any gotchas
6. Atomic commit with semantic message (see AGENTS.md commit conventions)

### If you are about to write more than 50 lines without running tests — stop.
Write a test first, then continue.

### If the same file has been edited 3 times in the same session — stop.
Something is wrong architecturally. Write a 2-sentence diagnosis before continuing.

### If you are creating a new utility function — check first.
Does `app/services/`, `app/utils/`, or an existing model method already do this?
Agents love creating duplicate helpers. Check before creating.

---

## WHAT THIS PROJECT IS NOT

Do not add any of the following without an explicit instruction to do so:

- ❌ Clinical decision support (no symptom analysis, no drug interactions, no diagnosis flows)
- ❌ Prescription generation or sharing
- ❌ Patient-facing login system or patient portal (everything is WhatsApp-only for patients)
- ❌ EMR / medical records storage (we store scheduling data, not clinical data)
- ❌ Automated clinical advice in bot responses
- ❌ Any flow that sends patient data to third parties not listed in AGENTS.md

If a flow step would require providing medical advice, the bot response must redirect:
`"Iske baare mein apne doctor se zaroor poochhen."`
