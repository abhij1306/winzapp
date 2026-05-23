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

## Gotchas

- Meta retries if the webhook does not return HTTP 200 quickly.
- Free-form outbound messages are allowed only inside the 24-hour customer service window.
- Template messages must be approved before scheduler jobs rely on them.
