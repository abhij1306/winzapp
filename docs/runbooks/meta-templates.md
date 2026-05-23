# Meta Template Registration

Pilot template payloads live in `scripts/register_meta_templates.py`.

Dry-run first:

```bash
.\.venv\Scripts\python.exe scripts/register_meta_templates.py
```

The scaffold covers:

- `fasting_reminder` — `UTILITY`
- `report_ready` — `UTILITY`
- `recall_reminder` — `MARKETING`
- `review_request` — `MARKETING`
- `daily_digest` — `UTILITY`, with Meta body examples for `{{1}}`, `{{2}}`, and `{{3}}`

Dry-run validates payload shape locally, including duplicate names, allowed categories, a single `BODY`
component, and examples for variable templates. Real registration must use a valid WABA ID and Meta
access token. Do not call Meta from automated tests.
