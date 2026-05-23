import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.intent_router import classify_diagnostics_intent


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("message", "expected_intent"),
    [
        ("CBC blood test book karna hai", "test_booking"),
        ("Home sample collection kal morning chahiye", "home_collection"),
        ("Mera report ready hai kya?", "report_inquiry"),
        ("Booking cancel karo please", "cancel"),
    ],
)
async def test_rule_first_router_classifies_patient_diagnostics_intents(
    db_session: AsyncSession,
    message: str,
    expected_intent: str,
) -> None:
    result = await classify_diagnostics_intent(message, "clinic-1", db_session)

    assert result.intent == expected_intent
    assert result.source == "rule"


@pytest.mark.asyncio
async def test_admin_messages_are_classified_only_for_admin_context(
    db_session: AsyncSession,
) -> None:
    admin_result = await classify_diagnostics_intent(
        "Aaj ke tests aur pending reports dikhao",
        "clinic-1",
        db_session,
        is_admin=True,
    )
    patient_result = await classify_diagnostics_intent(
        "Aaj ke tests aur pending reports dikhao",
        "clinic-1",
        db_session,
        is_admin=False,
    )

    assert admin_result.intent == "admin"
    assert admin_result.source == "rule"
    assert patient_result.intent == "report_inquiry"


@pytest.mark.asyncio
async def test_appointment_request_is_unknown_for_diagnostics_pilot(
    db_session: AsyncSession,
) -> None:
    result = await classify_diagnostics_intent(
        "Doctor appointment book karna hai",
        "clinic-1",
        db_session,
    )

    assert result.intent == "unknown"
    assert result.source == "rule"


@pytest.mark.asyncio
async def test_llm_fallback_is_skipped_when_feature_flag_is_disabled(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def cached_clinic(_clinic_id: str, _db: AsyncSession) -> dict[str, object]:
        return {"settings": {"features": {"llm_intent_fallback": False}}}

    async def fail_llm(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("LLM fallback must not run")

    monkeypatch.setattr("app.services.intent_router.get_clinic_by_id_cached", cached_clinic)
    monkeypatch.setattr("app.services.intent_router.llm_service.classify_intent", fail_llm)

    result = await classify_diagnostics_intent("Need help", "clinic-1", db_session)

    assert result.intent == "unknown"
    assert result.source == "rule"


@pytest.mark.asyncio
async def test_llm_fallback_runs_when_feature_flag_is_enabled(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def cached_clinic(_clinic_id: str, _db: AsyncSession) -> dict[str, object]:
        return {"settings": {"features": {"llm_intent_fallback": True}}}

    async def classify_with_llm(
        message_text: str,
        clinic_context: dict[str, object] | None = None,
    ) -> str:
        assert message_text == "Need help"
        assert clinic_context == {"clinic_id": "clinic-1"}
        return "report_inquiry"

    monkeypatch.setattr("app.services.intent_router.get_clinic_by_id_cached", cached_clinic)
    monkeypatch.setattr("app.services.intent_router.llm_service.classify_intent", classify_with_llm)

    result = await classify_diagnostics_intent("Need help", "clinic-1", db_session)

    assert result.intent == "report_inquiry"
    assert result.source == "llm"


@pytest.mark.asyncio
async def test_invalid_llm_intent_falls_back_to_unknown(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def cached_clinic(_clinic_id: str, _db: AsyncSession) -> dict[str, object]:
        return {"settings": {"features": {"llm_intent_fallback": True}}}

    async def classify_with_llm(
        _message_text: str,
        _clinic_context: dict[str, object] | None = None,
    ) -> str:
        return "appointment"

    monkeypatch.setattr("app.services.intent_router.get_clinic_by_id_cached", cached_clinic)
    monkeypatch.setattr("app.services.intent_router.llm_service.classify_intent", classify_with_llm)

    result = await classify_diagnostics_intent("Need help", "clinic-1", db_session)

    assert result.intent == "unknown"
    assert result.source == "llm"
