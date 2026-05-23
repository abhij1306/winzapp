from dataclasses import dataclass
from functools import lru_cache

import httpx

from app.config import Settings
from app.utils.logger import get_logger

KNOWN_INTENTS = {
    "appointment",
    "test_booking",
    "report_inquiry",
    "home_collection",
    "cancel",
    "admin",
    "unknown",
}
GROQ_CHAT_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"
logger = get_logger(__name__)


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    model: str
    api_key: str
    timeout_seconds: int


@lru_cache
def get_llm_config() -> LLMConfig:
    settings = Settings()
    return LLMConfig(
        provider=settings.llm_provider,
        model=settings.llm_model,
        api_key=settings.groq_api_key,
        timeout_seconds=settings.llm_timeout_seconds,
    )


async def classify_intent(
    message_text: str,
    clinic_context: dict[str, object] | None = None,
) -> str:
    config = get_llm_config()
    if not config.api_key or config.provider != "groq":
        return "unknown"

    prompt = (
        "Classify this WhatsApp clinic message into exactly one label: "
        f"{', '.join(sorted(KNOWN_INTENTS))}. Message: {message_text}"
    )
    response = await groq_completion(prompt, config, clinic_context)
    normalized = response.strip().lower()
    return normalized if normalized in KNOWN_INTENTS else "unknown"


async def draft_review_reply(
    review_text: str,
    clinic_context: dict[str, object] | None = None,
) -> str:
    config = get_llm_config()
    if not config.api_key or config.provider != "groq":
        return ""

    prompt = (
        "Draft a short, polite clinic owner reply in Hinglish or English, matching the review. "
        f"Review: {review_text}"
    )
    return await groq_completion(prompt, config, clinic_context)


async def groq_completion(
    prompt: str,
    config: LLMConfig,
    clinic_context: dict[str, object] | None,
) -> str:
    try:
        async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
            response = await client.post(
                GROQ_CHAT_COMPLETIONS_URL,
                headers={"Authorization": f"Bearer {config.api_key}"},
                json=groq_payload(prompt, config.model, clinic_context),
            )
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        logger.error("llm.request_failed", provider=config.provider, error=str(exc))
        return ""

    return extract_message_content(payload)


def groq_payload(
    prompt: str,
    model: str,
    clinic_context: dict[str, object] | None,
) -> dict[str, object]:
    context = clinic_context or {}
    return {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": "You are a concise classifier for clinic automation."},
            {"role": "user", "content": f"Context: {context}\n\n{prompt}"},
        ],
    }


def extract_message_content(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""

    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return ""

    message = first_choice.get("message")
    if not isinstance(message, dict):
        return ""

    content = message.get("content")
    return content if isinstance(content, str) else ""
