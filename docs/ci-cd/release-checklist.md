# Pilot Release Checklist

Use this checklist for the diagnostics pilot cutover. Record the command output or screenshot link beside each item before marking it done.

## Local Gate

- [ ] Start local services: `docker compose up -d postgres redis`
- [ ] Apply migrations: `.\.venv\Scripts\python.exe -m alembic upgrade head`
- [ ] Run backend tests: `.\.venv\Scripts\python.exe -m pytest`
- [ ] Run type checks: `.\.venv\Scripts\python.exe -m mypy app/`
- [ ] Run lint: `.\.venv\Scripts\python.exe -m ruff check app/`
- [ ] Build dashboard: `cd frontend; npm run build`
- [ ] Run dashboard tests: `cd frontend; npm test`

## Deployment Gate

- [ ] Railway environment variables configured.
- [ ] One Railway web replica configured.
- [ ] Migrations run successfully.
- [ ] `/health` returns green.
- [ ] Scheduler heartbeat visible in Redis at `scheduler:heartbeat`.
- [ ] `SENTRY_DSN` or `LOGFIRE_TOKEN` configured for the pilot environment.

## WhatsApp Gate

- [ ] Webhook URL registered in Meta dashboard.
- [ ] GET verification passes.
- [ ] Valid inbound message gets a response.
- [ ] Invalid signature returns 403.
- [ ] Duplicate message is ACKed once and not reprocessed.
- [ ] Flow exception creates `failed_messages` entry.
- [ ] Meta template names match the approved template list.

## Pilot Operations Gate

- [ ] Pilot clinic seeded.
- [ ] Test catalog seeded.
- [ ] Owner OTP login works.
- [ ] Dashboard overview, bookings, pending reports, failed messages, patients, catalog, and settings pages load.
- [ ] Report upload sends WhatsApp document.
- [ ] Failed message retry works.
- [ ] RLS isolation test passes.
- [ ] Owner knows fallback manual WhatsApp process.

## Observability Gate

- [ ] Webhook latency alert fires when `WEBHOOK_LATENCY_ALERT_MS` is temporarily set below observed latency.
- [ ] WhatsApp delivery failure alert fires when Meta returns a non-2xx response in staging.
- [ ] Scheduler heartbeat missed alert fires after deleting `scheduler:heartbeat` in staging Redis.
- [ ] Structured logs include `request_id`, `method`, `path`, and event-specific fields.
- [ ] Logs mask patient WhatsApp numbers to the last four digits only.

## Rollback Gate

- [ ] Previous Railway deployment is known and can be redeployed.
- [ ] Report upload can be handled manually through the clinic's WhatsApp number.
- [ ] Failed messages can be replayed after rollback or acknowledged manually.
- [ ] Pilot owner has the support phone number and escalation window.
