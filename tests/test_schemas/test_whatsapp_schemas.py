import pytest
from pydantic import ValidationError

from app.schemas.whatsapp_webhook import WAMessage, WAWebhookPayload


def test_wa_message_aliases_from_to_from_() -> None:
    message = WAMessage.model_validate(
        {
            "id": "wamid.TEST",
            "from": "919876543210",
            "timestamp": "1716450000",
            "type": "text",
            "text": {"body": "hello"},
        },
    )

    assert message.from_ == "919876543210"


def test_wa_message_rejects_unsupported_message_type() -> None:
    with pytest.raises(ValidationError):
        WAMessage.model_validate(
            {
                "id": "wamid.TEST",
                "from": "919876543210",
                "timestamp": "1716450000",
                "type": "sticker",
            },
        )


def test_webhook_payload_rejects_non_whatsapp_object() -> None:
    with pytest.raises(ValidationError):
        WAWebhookPayload.model_validate({"object": "page", "entry": []})


def test_webhook_payload_accepts_whatsapp_object() -> None:
    payload = WAWebhookPayload.model_validate({"object": "whatsapp_business_account", "entry": []})

    assert payload.object == "whatsapp_business_account"
