# Data Model

The schema is multi-tenant from the first migration. Every tenant-scoped table has `clinic_id`, and every patient/booking/session query filters by `clinic_id`.

## Pilot MVP Tables

| Table | Phase | Notes |
|---|---:|---|
| `clinics` | Pilot MVP | Tenant root, WhatsApp config, settings JSONB, feature flags. |
| `patients` | Pilot MVP | Unique `(clinic_id, whatsapp_number)`, consent fields. |
| `doctors` | Pilot MVP | Included for future appointment support. |
| `appointment_slots` | Pilot MVP | Included for future appointment support. |
| `appointments` | Pilot MVP | Data model only during diagnostics pilot. |
| `tests` | Pilot MVP | Diagnostics catalog. |
| `test_bookings` | Pilot MVP | Core booking workflow. |
| `conversation_sessions` | Pilot MVP | Source of truth for flow state. |
| `messages` | Pilot MVP | Inbound/outbound message log and idempotency. |
| `failed_messages` | Pilot MVP | Dead-letter queue and retry source. |
| `audit_log` | Pilot MVP | 7-year traceability. |
| `recall_schedules` | Pilot MVP | Diagnostics recall automation. |
| `reviews` | Pilot MVP | Review request tracking; GBP later. |
| `broadcasts` | Post-pilot | Feature-flagged campaign support. |

## Mixins

- Mutable models inherit `SoftDeleteMixin`.
- Immutable/log tables inherit `TimestampMixin` only where deletion is not part of normal lifecycle.
- `updated_at` uses both `server_default=func.now()` and `onupdate=func.now()`.

## Migration Requirements

- Enable `pgcrypto` for `gen_random_uuid()`.
- Create `set_updated_at()` and attach it to mutable tables.
- Enable RLS on tenant patient/booking/session/message tables.
- Manually review JSONB defaults because Alembic autogenerate can miss JSONB default changes.
