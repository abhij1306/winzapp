# Meta Template Registration

Pilot template payloads live in `scripts/register_meta_templates.py`.

Dry-run first:

```bash
.\.venv\Scripts\python.exe scripts/register_meta_templates.py
```

The scaffold covers:

- `fasting_reminder`
- `report_ready`
- `recall_reminder`
- `review_request`
- `daily_digest`

Real registration must use a valid WABA ID and Meta access token. Do not call Meta from automated tests.
