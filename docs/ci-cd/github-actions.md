# GitHub Actions

Repository: `abhij1306/winzapp`

Commit author email for this project: `abhij1306@gmail.com`

## Required Workflow

On push and pull request:

1. Start PostgreSQL service.
2. Start Redis service.
3. Install Python dependencies.
4. Run `alembic upgrade head`.
5. Run `pytest`.
6. Run `mypy app/`.
7. Run `ruff check app/`.

## Required Secrets

Pilot CI should avoid real external API calls. Use fake values unless a deploy job needs real credentials.

```text
DATABASE_URL
REDIS_URL
WA_APP_SECRET
WA_VERIFY_TOKEN
LLM_PROVIDER
LLM_MODEL
GROQ_API_KEY
SUPABASE_URL
SUPABASE_SERVICE_KEY
```

Deploy secrets are configured in Railway, not committed to GitHub.
