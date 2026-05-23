import pytest

from app.services.llm_service import classify_intent, draft_review_reply, get_llm_config


def test_llm_config_loads_provider_and_model() -> None:
    config = get_llm_config()

    assert config.provider == "groq"
    assert config.model


@pytest.mark.asyncio
async def test_classify_intent_returns_unknown_without_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "")
    get_llm_config.cache_clear()

    result = await classify_intent("blood test karwana hai")

    assert result == "unknown"


@pytest.mark.asyncio
async def test_draft_review_reply_returns_empty_string_without_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "")
    get_llm_config.cache_clear()

    result = await draft_review_reply("Good service")

    assert result == ""
