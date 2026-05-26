# Local Development Runbook

## Setup

```bash
cp .env.example .env
docker compose up -d postgres redis
docker compose ps
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m scripts.seed_pilot
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Use the project `.venv` for all local Python commands. Do not install project dependencies globally.
Compose retains PostgreSQL data in `postgres_data`; Redis has no data volume because cached values can be rebuilt from PostgreSQL.

## Required Environment

```env
DATABASE_URL=postgresql+asyncpg://winzapp:winzapp@localhost:55432/winzapp
REDIS_URL=redis://localhost:6379/0
WA_APP_SECRET=
WA_VERIFY_TOKEN=
LLM_PROVIDER=groq
LLM_MODEL=llama-3.3-70b-versatile
GROQ_API_KEY=
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
JWT_SECRET=
```

Use fake external credentials for tests. Real Meta/Groq/Supabase calls must be mocked in automated tests.
