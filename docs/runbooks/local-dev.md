# Local Development Runbook

## Setup

```bash
cp .env.example .env
docker compose up -d postgres redis
pip install -r requirements.txt
alembic upgrade head
python scripts/seed_pilot.py
uvicorn app.main:app --reload --port 8000
```

## Required Environment

```env
DATABASE_URL=
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
