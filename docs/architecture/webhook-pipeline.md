# WhatsApp Webhook Pipeline

The incoming webhook order is fixed.

1. Verify Meta signature.
2. Resolve clinic by `phone_number_id` through cache and set `app.clinic_id`.
3. Check idempotency by tenant-scoped `messages.wa_message_id`.
4. Log inbound message to `messages`.
5. Load or create conversation session through cache.
6. Run consent flow if this is the first patient message.
7. Route message through intent router and flow engine.
8. Send WhatsApp response.
9. On exception, write `failed_messages` and return HTTP 200 to Meta.

Invalid signatures return 403. All other non-validation failures should be captured and ACKed so Meta does not repeatedly redeliver the same message.

## Idempotency

Duplicate `wa_message_id` values are silently ACKed with no flow execution and no duplicate
outbound messages. The lookup includes `clinic_id` because `messages` is RLS-protected.

## Cache Rules

Webhook and flow hot paths never read clinic config, test catalog, or conversation sessions directly from DB. They use:

- `get_clinic_cached(phone_number_id, db)`
- `get_tests_cached(clinic_id, db)`
- `get_session_cached(wa_number, clinic_id, db)`

Session writes are write-through: DB and Redis are updated together.
