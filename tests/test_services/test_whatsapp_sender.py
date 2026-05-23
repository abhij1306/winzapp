import httpx
import pytest
import respx

from app.services.whatsapp_sender import (
    WADeliveryError,
    send_interactive_buttons,
    send_interactive_list,
    send_text,
)


@pytest.mark.asyncio
@respx.mock
async def test_send_text_posts_expected_payload() -> None:
    route = respx.post("https://graph.facebook.com/v18.0/phone-123/messages").mock(
        return_value=httpx.Response(200, json={"messages": [{"id": "wamid.OUT"}]}),
    )

    result = await send_text("phone-123", "+919876543210", "token", "Hello")

    assert result["messages"][0]["id"] == "wamid.OUT"
    assert route.called
    payload = route.calls.last.request.content.decode()
    assert '"type":"text"' in payload
    assert '"body":"Hello"' in payload


@pytest.mark.asyncio
@respx.mock
async def test_send_text_raises_delivery_error_on_meta_failure() -> None:
    respx.post("https://graph.facebook.com/v18.0/phone-123/messages").mock(
        return_value=httpx.Response(500, json={"error": {"message": "Meta failed"}}),
    )

    with pytest.raises(WADeliveryError):
        await send_text("phone-123", "+919876543210", "token", "Hello")


@pytest.mark.asyncio
async def test_interactive_list_enforces_ten_items_per_section() -> None:
    rows = [{"id": str(index), "title": f"Item {index}"} for index in range(11)]

    with pytest.raises(ValueError, match="10 items"):
        await send_interactive_list(
            "phone-123",
            "+919876543210",
            "token",
            "Choose",
            [{"title": "Tests", "rows": rows}],
        )


@pytest.mark.asyncio
async def test_interactive_buttons_enforces_three_button_limit() -> None:
    buttons = [{"id": str(index), "title": f"Button {index}"} for index in range(4)]

    with pytest.raises(ValueError, match="3 buttons"):
        await send_interactive_buttons("phone-123", "+919876543210", "token", "Choose", buttons)
