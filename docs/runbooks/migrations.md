# Migrations Runbook

## Create Migration

```bash
alembic revision --autogenerate -m "description"
```

Then manually review:

- JSONB defaults.
- RLS policies.
- `set_updated_at()` triggers.
- `pgcrypto` extension.
- Indexes and unique constraints.
- `ondelete` behavior for foreign keys.

## Apply Migration

```bash
alembic upgrade head
```

CI must run this against a disposable PostgreSQL service before tests.
