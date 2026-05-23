# WhatsApp Meta Runbook

## Pilot Setup

1. Verify Meta Business Manager.
2. Create or connect WhatsApp Business Account.
3. Approve display name.
4. Register phone number not currently used by personal WhatsApp.
5. Configure webhook URL.
6. Verify webhook challenge.
7. Submit required templates for approval.
8. Switch app to Live mode before messaging real patients.

## Local Testing

Use ngrok or equivalent:

```bash
ngrok http 8000
```

Register the HTTPS forwarding URL as the Meta webhook URL.

After seeding the pilot clinic, replace `settings.wa_phone_number_id` value
`pilot-wa-phone-number-id` with the Meta phone number ID used for this webhook. Incoming
messages cannot resolve to the pilot clinic until those values match.

The local one-participant smoke sequence is:

1. Start PostgreSQL, Redis, the API, and dashboard from `README.md`.
2. Set `WA_APP_SECRET`, `WA_VERIFY_TOKEN`, and `WA_ACCESS_TOKEN` in `.env`.
3. Start the HTTPS tunnel and register `<tunnel-url>/webhooks/whatsapp` in Meta.
4. Send an inbound message from the opted-in test phone and complete consent.
5. Exercise booking, report inquiry/cancellation, report upload, failed-message retry, and
   scheduler heartbeat verification before using a real patient.
6. Set the test patient to opted out and confirm automated report delivery is blocked so staff
   use the manual sharing fallback.

## Gotchas

- Meta retries if the webhook does not return HTTP 200 quickly.
- Free-form outbound messages are allowed only inside the 24-hour customer service window.
- Template messages must be approved before scheduler jobs rely on them.
- `POST /api/v1/report-ready` requires the owner bearer token from OTP verification.
- Report upload and report-ready delivery refuse automated WhatsApp sends after patient opt-out.
