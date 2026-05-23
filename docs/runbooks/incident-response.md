# Incident Response Runbook

## Webhook Latency Alert

1. Check `/health`.
2. Check DB and Redis connectivity.
3. Check recent logs for slow cache misses or external API timeouts.
4. Confirm Railway has only one web replica during Pilot MVP.
5. If flow failures increased, inspect `failed_messages`.

## WhatsApp Delivery Failure Alert

1. Confirm Meta API status and credentials.
2. Check template approval status if the failed message used a template.
3. Verify clinic WhatsApp phone number and access token.
4. Retry failed messages from dashboard when safe.

## Missed Scheduler Heartbeat

1. Check app process health.
2. Confirm scheduler started during app startup.
3. Confirm timezone is `Asia/Kolkata`.
4. Restart Railway service if scheduler is stopped.
5. Review idempotent jobs after restart.
