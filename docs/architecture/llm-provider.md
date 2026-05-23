# LLM Provider Architecture

## Decision

Use a small LLM provider abstraction with Groq as the default provider.

The application calls project-level functions from `app/services/llm_service.py`:

- `classify_intent(message_text: str, clinic_context: dict | None = None) -> str`
- `draft_review_reply(review_text: str, clinic_context: dict | None = None) -> str`

Provider-specific details stay inside the service module or a small provider helper. Flow code must not import Groq SDKs directly.

## Configuration

Configuration is loaded from `.env` through `app/config.py`.

```env
LLM_PROVIDER=groq
LLM_MODEL=llama-3.3-70b-versatile
GROQ_API_KEY=
LLM_TIMEOUT_SECONDS=10
LLM_INTENT_FALLBACK_ENABLED=true
```

If a provider changes later, the public app functions stay stable.

## Runtime Rules

- Rule-based routing runs first.
- LLM fallback runs only when rule-based routing returns `unknown` and the clinic feature flag `llm_intent_fallback` is enabled.
- LLM output is constrained to known intent labels.
- LLM failures do not crash the webhook path. The router returns `unknown`, logs the failure with masked PII, and can write to `failed_messages` when appropriate.
- Patient data sent to the LLM must be minimal and purpose-bound.

## Testing Rules

- Tests mock `app.services.llm_service`, not the Groq API.
- No test may call a real LLM provider.
- Provider selection and missing API key behavior must have unit tests.
