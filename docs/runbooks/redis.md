# Redis Runbook

Redis is mandatory in every environment.

## Cached Data

- Clinic config by WhatsApp `phone_number_id`.
- Test catalog by `clinic_id`.
- Conversation session by `clinic_id` and patient WhatsApp number.

## Rules

- JSON serialize all values.
- Use TTL for session data.
- Never store Python objects directly.
- On cache miss, read DB and repopulate Redis.
- On session write, update DB and Redis together.
- On clinic/test settings changes, invalidate relevant keys.
