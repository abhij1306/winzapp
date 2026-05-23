# Hetzner Production Path

Hetzner plus Docker Compose is the Post-pilot production path.

## Target Shape

- Nginx or Caddy reverse proxy with TLS.
- FastAPI web container.
- Scheduler/worker container after the APScheduler migration.
- PostgreSQL.
- Redis.
- Object storage integration through `app/services/storage.py`.

## Not Pilot MVP

Do not block the diagnostics pilot on Hetzner deployment. Keep this document current so production migration is planned, but execute Railway first.
