# Railway Deployment

Railway is the Pilot MVP deployment path.

## Pilot Constraints

- Run one web replica only.
- APScheduler runs inside the FastAPI process for Pilot MVP.
- Do not enable autoscaling while scheduler is in-process.
- Migrations run during deploy before the app starts serving traffic.

## Services

- FastAPI web service.
- PostgreSQL.
- Redis.

Dashboard hosting can be Railway or Vercel, but the Pilot MVP backend deployment target is Railway.

## Health Check

`GET /health` must return:

```json
{
  "status": "ok",
  "db": "ok",
  "redis": "ok",
  "scheduler": "ok"
}
```

If any dependency is degraded, return `"status": "degraded"` with the failing component marked.
