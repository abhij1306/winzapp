from typing import cast

import httpx

WA_API_URL = "https://graph.facebook.com/v18.0/{phone_number_id}/messages"


class WADeliveryError(RuntimeError):
    pass


async def send_text(
    phone_number_id: str,
    to: str,
    access_token: str,
    body: str,
) -> dict[str, object]:
    return await post_message(
        phone_number_id,
        access_token,
        {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": body},
        },
    )


async def send_interactive_list(
    phone_number_id: str,
    to: str,
    access_token: str,
    body: str,
    sections: list[dict[str, object]],
) -> dict[str, object]:
    validate_list_sections(sections)
    return await post_message(
        phone_number_id,
        access_token,
        {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "body": {"text": body},
                "action": {"button": "Select", "sections": sections},
            },
        },
    )


async def send_interactive_buttons(
    phone_number_id: str,
    to: str,
    access_token: str,
    body: str,
    buttons: list[dict[str, str]],
) -> dict[str, object]:
    if len(buttons) > 3:
        raise ValueError("WhatsApp button replies support at most 3 buttons")

    return await post_message(
        phone_number_id,
        access_token,
        {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body},
                "action": {"buttons": [button_payload(button) for button in buttons]},
            },
        },
    )


async def send_document(
    phone_number_id: str,
    to: str,
    access_token: str,
    document_url: str,
    filename: str,
    caption: str | None = None,
) -> dict[str, object]:
    document: dict[str, object] = {"link": document_url, "filename": filename}
    if caption is not None:
        document["caption"] = caption

    return await post_message(
        phone_number_id,
        access_token,
        {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "document",
            "document": document,
        },
    )


async def send_template(
    phone_number_id: str,
    to: str,
    access_token: str,
    template_name: str,
    language_code: str,
    components: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    template: dict[str, object] = {
        "name": template_name,
        "language": {"code": language_code},
    }
    if components is not None:
        template["components"] = components

    return await post_message(
        phone_number_id,
        access_token,
        {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": template,
        },
    )


async def post_message(
    phone_number_id: str,
    access_token: str,
    payload: dict[str, object],
) -> dict[str, object]:
    url = WA_API_URL.format(phone_number_id=phone_number_id)
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            json=payload,
        )

    if response.status_code >= 400:
        raise WADeliveryError(f"WhatsApp delivery failed: {response.text}")

    return cast(dict[str, object], response.json())


def validate_list_sections(sections: list[dict[str, object]]) -> None:
    for section in sections:
        rows = section.get("rows")
        if isinstance(rows, list) and len(rows) > 10:
            raise ValueError("WhatsApp list sections support at most 10 items")


def button_payload(button: dict[str, str]) -> dict[str, object]:
    return {
        "type": "reply",
        "reply": {
            "id": button["id"],
            "title": button["title"],
        },
    }
