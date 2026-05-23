# Pilot Readiness Review - 2026-05-23

## Scope

End-to-end diagnostics MVP readiness review covering inbound WhatsApp routing, tenant
isolation, report delivery, dashboard login, scheduler lifecycle, observability health, and
release-gate documentation.

## Decisions Applied

| Finding | Severity | Decision |
| --- | --- | --- |
| Live inbound messages stopped at consent-only routing and scheduler did not start on API lifecycle. | Critical | Use shared flow dispatch for webhook/retry and start one in-process scheduler on app lifespan. |
| Dashboard OTP payload contained `clinic_id`, rejected by strict auth request schemas. | Critical | Keep backend contract minimal and send only accepted OTP fields from the dashboard. |
| `POST /api/v1/report-ready` could deliver a patient report without owner authentication. | Critical | Require the same owner bearer token and tenant authorization used by dashboard operations. |
| Report delivery APIs and the admin send command could send PDFs after a patient opted out. | Critical | Reject automated report delivery for opted-out patients and direct staff to manual sharing. |
| Strict request-schema failures returned FastAPI's default shape instead of the documented API error envelope. | High | Install a validation exception handler that returns `ErrorEnvelope` without reflecting submitted values. |
| Webhook idempotency accessed RLS-protected `messages` without clinic scope. | High | Resolve clinic first, set tenant context, and filter idempotency by `clinic_id`. |
| Multi-commit request and scheduler paths could lose or leak PostgreSQL tenant context. | High | Set session tenant context for the operation and clear it before the connection returns to the pool. |
| `/health` did not report the scheduler heartbeat required by observability acceptance criteria. | High | Include `scheduler` status based on the Redis heartbeat key. |
| Release documentation used stale routes and omitted Meta phone-number replacement. | Medium | Update README, webhook runbook, and traceability map. |

## Verification Gates

- Passed: `.\scripts\local_ci.ps1` (Docker services, migrations, 158 backend tests, mypy, Ruff).
- Passed: `npm test -- --run`, `npm run build`, and `npm run lint` in `frontend/`.
- Passed: migrated PostgreSQL RLS isolation regression using a temporary non-owner role.
- External smoke gates remain pending until Meta, Supabase, template approval, tunnel/deployment,
  and observability credentials are available.
