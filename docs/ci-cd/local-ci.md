# Local CI

Supported local path uses Docker Compose for real PostgreSQL and Redis.

## Required Commands

```bash
docker compose up -d postgres redis
alembic upgrade head
pytest
mypy app/
ruff check app/
```

Run the same checks before marking any task complete.

## Rules

- Do not mock database operations in tests.
- Do not mock Redis operations in tests.
- Do mock external HTTP services: Meta, Groq, Supabase Storage, Razorpay, Google APIs.
- Run migrations before tests so schema drift is caught early.
