# Local CI

Supported local path uses Docker Compose for real PostgreSQL and Redis.

Local PostgreSQL maps to `localhost:55432` to avoid collisions with developer machines that already run Postgres on `5432`.

## Required Commands

```bash
docker compose up -d postgres redis
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m mypy app/
.\.venv\Scripts\python.exe -m ruff check app/
```

Run the same checks before marking any task complete.

## Rules

- Do not mock database operations in tests.
- Do not mock Redis operations in tests.
- Do mock external HTTP services: Meta, Groq, Supabase Storage, Razorpay, Google APIs.
- Run migrations before tests so schema drift is caught early.
