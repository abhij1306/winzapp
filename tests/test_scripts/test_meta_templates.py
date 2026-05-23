import pytest

from scripts.register_meta_templates import build_template_payloads, validate_template_payloads


def payload_by_name() -> dict[str, dict[str, object]]:
    return {str(payload["name"]): payload for payload in build_template_payloads()}


def test_template_categories_match_message_intent() -> None:
    payloads = payload_by_name()

    assert payloads["fasting_reminder"]["category"] == "UTILITY"
    assert payloads["report_ready"]["category"] == "UTILITY"
    assert payloads["daily_digest"]["category"] == "UTILITY"
    assert payloads["recall_reminder"]["category"] == "MARKETING"
    assert payloads["review_request"]["category"] == "MARKETING"


def test_variable_templates_include_body_examples() -> None:
    daily_digest = payload_by_name()["daily_digest"]
    body = next(
        component
        for component in daily_digest["components"]
        if isinstance(component, dict) and component.get("type") == "BODY"
    )

    assert body["example"] == {"body_text": [["28", "6", "22"]]}


def test_template_payload_validation_accepts_pilot_payloads() -> None:
    validate_template_payloads(build_template_payloads())


def test_template_payload_validation_rejects_missing_variable_examples() -> None:
    invalid_payload = {
        "name": "daily_digest",
        "language": "en_US",
        "category": "UTILITY",
        "components": [{"type": "BODY", "text": "Daily: {{1}} tests"}],
    }

    with pytest.raises(ValueError, match="daily_digest"):
        validate_template_payloads([invalid_payload])
