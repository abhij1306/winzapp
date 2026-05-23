# Release Checklist

## Local Gate

- [ ] `docker compose up -d postgres redis`
- [ ] `alembic upgrade head`
- [ ] `pytest`
- [ ] `mypy app/`
- [ ] `ruff check app/`

## Deployment Gate

- [ ] Railway environment variables configured.
- [ ] One Railway web replica configured.
- [ ] Migrations run successfully.
- [ ] `/health` returns green.
- [ ] Scheduler heartbeat visible.

## WhatsApp Gate

- [ ] Webhook URL registered in Meta dashboard.
- [ ] GET verification passes.
- [ ] Valid inbound message gets a response.
- [ ] Invalid signature returns 403.
- [ ] Duplicate message is ACKed once and not reprocessed.
- [ ] Flow exception creates `failed_messages` entry.

## Pilot Operations Gate

- [ ] Pilot clinic seeded.
- [ ] Test catalog seeded.
- [ ] Owner OTP login works.
- [ ] Report upload sends WhatsApp document.
- [ ] Failed message retry works.
- [ ] RLS isolation test passes.
- [ ] Owner knows fallback manual WhatsApp process.
