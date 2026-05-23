import hashlib
import hmac
import json
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.flows.base_flow import FlowMessage
from app.main import app
from app.models import Clinic, FailedMessage, Message
from app.webhooks import whatsapp as whatsapp_webhook

SECRET = "test-secret"
VERIFY_TOKEN = "verify-token"
ACCESS_TOKEN = "access-token"
PHONE_NUMBER_ID = "phone-123"


@pytest_asyncio.fixture
async def redis_client() -> Redis:
    client = Redis.from_url(get_settings().redis_url, decode_responses=True)
    await client.flushdb()
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()


@pytest.fixture(autouse=True)
def webhook_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        whatsapp_webhook,
        "get_settings",
        lambda: SimpleNamespace(
            wa_app_secret=SECRET,
            wa_verify_token=VERIFY_TOKEN,
            wa_access_token=ACCESS_TOKEN,
        ),
    )


@pytest_asyncio.fixture
async def webhook_client(db_session: AsyncSession) -> httpx.AsyncClient:
    async def override_get_db() -> AsyncSession:
        return db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


def signed_headers(raw_body: bytes, secret: str = SECRET) -> dict[str, str]:
    digest = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return {"X-Hub-Signature-256": f"sha256={digest}"}


def webhook_body(message_id: str = "wamid-1", text: str = "Hi") -> bytes:
    return json.dumps(
        {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "waba-1",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "919000000001",
                                    "phone_number_id": PHONE_NUMBER_ID,
                                },
                                "contacts": [
                                    {"wa_id": "919999999999", "profile": {"name": "Patient"}}
                                ],
                                "messages": [
                                    {
                                        "from": "919999999999",
                                        "id": message_id,
                                        "timestamp": "1730000000",
                                        "type": "text",
                                        "text": {"body": text},
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        },
    ).encode()


async def create_clinic(db_session: AsyncSession) -> Clinic:
    clinic = Clinic(
        id=uuid4(),
        name="Demo Diagnostics",
        whatsapp_number="+919000000001",
        owner_whatsapp="+919000000002",
        clinic_type="diagnostic",
        settings={"wa_phone_number_id": PHONE_NUMBER_ID},
    )
    db_session.add(clinic)
    await db_session.commit()
    return clinic


@pytest.mark.asyncio
async def test_get_verification_challenge_returns_challenge(
    webhook_client: httpx.AsyncClient,
) -> None:
    response = await webhook_client.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": VERIFY_TOKEN,
            "hub.challenge": "challenge-123",
        },
    )

    assert response.status_code == 200
    assert response.text == "challenge-123"


@pytest.mark.asyncio
async def test_invalid_signature_returns_403_without_writing_message(
    db_session: AsyncSession,
    webhook_client: httpx.AsyncClient,
    redis_client: Redis,
) -> None:
    await create_clinic(db_session)
    response = await webhook_client.post(
        "/webhooks/whatsapp",
        content=webhook_body(),
        headers=signed_headers(b"tampered"),
    )

    message_count = (
        await db_session.execute(select(func.count()).select_from(Message))
    ).scalar_one()

    assert response.status_code == 403
    assert message_count == 0


@pytest.mark.asyncio
async def test_duplicate_message_is_silently_acked(
    db_session: AsyncSession,
    webhook_client: httpx.AsyncClient,
    redis_client: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clinic = await create_clinic(db_session)
    db_session.add(
        Message(
            clinic_id=clinic.id,
            whatsapp_number="919999999999",
            direction="inbound",
            message_type="text",
            content="Hi",
            metadata_json={},
            wa_message_id="wamid-duplicate",
        ),
    )
    await db_session.commit()

    async def fail_flow(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("duplicate should not reach flow engine")

    monkeypatch.setattr(whatsapp_webhook.ConsentFlow, "handle", fail_flow)
    body = webhook_body(message_id="wamid-duplicate")
    response = await webhook_client.post(
        "/webhooks/whatsapp",
        content=body,
        headers=signed_headers(body),
    )

    message_count = (
        await db_session.execute(select(func.count()).select_from(Message))
    ).scalar_one()

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert message_count == 1


@pytest.mark.asyncio
async def test_valid_message_logs_inbound_routes_flow_and_sends_response(
    db_session: AsyncSession,
    webhook_client: httpx.AsyncClient,
    redis_client: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clinic = await create_clinic(db_session)
    clinic_id = clinic.id
    sent_messages: list[tuple[str, str, str, str]] = []

    async def fake_handle(
        _flow: object,
        _session: object,
        message: FlowMessage,
        _db: AsyncSession,
    ) -> str:
        assert message.clinic_id == str(clinic_id)
        assert message.whatsapp_number == "919999999999"
        assert message.text == "Hi"
        return "Consent prompt"

    async def fake_send_text(
        phone_number_id: str,
        to: str,
        access_token: str,
        body: str,
    ) -> dict[str, object]:
        sent_messages.append((phone_number_id, to, access_token, body))
        return {"messages": [{"id": "wamid-out"}]}

    monkeypatch.setattr(whatsapp_webhook.ConsentFlow, "handle", fake_handle)
    monkeypatch.setattr(whatsapp_webhook, "send_text", fake_send_text)
    body = webhook_body()

    response = await webhook_client.post(
        "/webhooks/whatsapp",
        content=body,
        headers=signed_headers(body),
    )

    message = (
        await db_session.execute(select(Message).where(Message.wa_message_id == "wamid-1"))
    ).scalar_one()

    assert response.status_code == 200
    assert message.clinic_id == clinic_id
    assert message.direction == "inbound"
    assert message.content == "Hi"
    assert sent_messages == [(PHONE_NUMBER_ID, "919999999999", ACCESS_TOKEN, "Consent prompt")]


@pytest.mark.asyncio
async def test_flow_exception_writes_failed_message_after_inbound_log(
    db_session: AsyncSession,
    webhook_client: httpx.AsyncClient,
    redis_client: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clinic = await create_clinic(db_session)
    clinic_id = clinic.id

    async def failing_handle(*_args: object, **_kwargs: object) -> str:
        raise RuntimeError("flow crashed")

    monkeypatch.setattr(whatsapp_webhook.ConsentFlow, "handle", failing_handle)
    body = webhook_body(message_id="wamid-fail")

    response = await webhook_client.post(
        "/webhooks/whatsapp",
        content=body,
        headers=signed_headers(body),
    )

    message = (
        await db_session.execute(select(Message).where(Message.wa_message_id == "wamid-fail"))
    ).scalar_one()
    failed = (
        await db_session.execute(
            select(FailedMessage).where(FailedMessage.wa_message_id == "wamid-fail"),
        )
    ).scalar_one()

    assert response.status_code == 200
    assert message.clinic_id == clinic_id
    assert failed.clinic_id == clinic_id
    assert failed.whatsapp_number == "919999999999"
    assert "flow crashed" in failed.error
