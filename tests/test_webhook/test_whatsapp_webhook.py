import hashlib
import hmac
import json
from datetime import UTC, datetime
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
from app.models import Clinic, ConversationSession, FailedMessage, Message, Patient, Test
from app.services import flow_engine
from app.templates.hinglish import ADMIN_UNKNOWN_COMMAND, render_category_prompt
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


def webhook_body(
    message_id: str = "wamid-1",
    text: str = "Hi",
    whatsapp_number: str = "919999999999",
) -> bytes:
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
                                    {"wa_id": whatsapp_number, "profile": {"name": "Patient"}}
                                ],
                                "messages": [
                                    {
                                        "from": whatsapp_number,
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


def live_like_webhook_body(
    message_id: str = "wamid-live-1",
    text: str = "Hi",
    whatsapp_number: str = "918999635679",
) -> bytes:
    return json.dumps(
        {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "1526553658862317",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "15556680547",
                                    "phone_number_id": PHONE_NUMBER_ID,
                                },
                                "contacts": [
                                    {
                                        "profile": {"name": "Abhineet"},
                                        "wa_id": whatsapp_number,
                                        "user_id": "IN.2809731156053320",
                                    }
                                ],
                                "messages": [
                                    {
                                        "from": whatsapp_number,
                                        "from_user_id": "IN.2809731156053320",
                                        "id": message_id,
                                        "timestamp": "1779773887",
                                        "text": {"body": text},
                                        "type": "text",
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        },
    ).encode()


def status_webhook_body(status: str = "delivered") -> bytes:
    return json.dumps(
        {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "1526553658862317",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "15556680547",
                                    "phone_number_id": PHONE_NUMBER_ID,
                                },
                                "contacts": [
                                    {
                                        "wa_id": "918999635679",
                                        "user_id": "IN.2809731156053320",
                                    }
                                ],
                                "statuses": [
                                    {
                                        "id": "wamid.status-1",
                                        "status": status,
                                        "timestamp": "1779774099",
                                        "recipient_id": "918999635679",
                                        "recipient_user_id": "IN.2809731156053320",
                                        "pricing": {
                                            "billable": False,
                                            "pricing_model": "PMP",
                                            "category": "service",
                                            "type": "free_customer_service",
                                        },
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


async def create_consented_patient_session(
    db_session: AsyncSession,
    clinic: Clinic,
    whatsapp_number: str = "919999999999",
) -> ConversationSession:
    patient = Patient(
        clinic_id=clinic.id,
        whatsapp_number=whatsapp_number,
        opt_in=True,
        opt_in_at=datetime.now(UTC),
    )
    session = ConversationSession(
        clinic_id=clinic.id,
        patient=patient,
        whatsapp_number=whatsapp_number,
        flow="consent",
        step="consent_granted",
        is_active=False,
        context={"automation_stopped": False},
    )
    db_session.add_all([patient, session])
    await db_session.commit()
    return session


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

    monkeypatch.setattr(flow_engine.ConsentFlow, "handle", fail_flow)
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
async def test_idempotency_lookup_is_scoped_to_resolved_clinic(
    db_session: AsyncSession,
) -> None:
    first_clinic = await create_clinic(db_session)
    second_clinic = Clinic(
        id=uuid4(),
        name="Other Diagnostics",
        whatsapp_number="+919000000003",
        owner_whatsapp="+919000000004",
        clinic_type="diagnostic",
        settings={"wa_phone_number_id": "phone-456"},
    )
    db_session.add_all(
        [
            second_clinic,
            Message(
                clinic_id=first_clinic.id,
                whatsapp_number="919999999999",
                direction="inbound",
                message_type="text",
                content="Hi",
                metadata_json={},
                wa_message_id="wamid-other-clinic",
            ),
        ],
    )
    await db_session.commit()

    found = await whatsapp_webhook.message_already_processed(
        db_session,
        "wamid-other-clinic",
        str(second_clinic.id),
    )

    assert found is False


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

    monkeypatch.setattr(flow_engine.ConsentFlow, "handle", fake_handle)
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
async def test_live_payload_with_extra_meta_fields_is_accepted(
    db_session: AsyncSession,
    webhook_client: httpx.AsyncClient,
    redis_client: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clinic = await create_clinic(db_session)
    clinic_id = clinic.id
    sent_messages: list[str] = []

    async def fake_handle(
        _flow: object,
        _session: object,
        message: FlowMessage,
        _db: AsyncSession,
    ) -> str:
        assert message.clinic_id == str(clinic_id)
        assert message.whatsapp_number == "918999635679"
        assert message.text == "Hi"
        return "Consent prompt"

    async def fake_send_text(
        _phone_number_id: str,
        _to: str,
        _access_token: str,
        body: str,
    ) -> dict[str, object]:
        sent_messages.append(body)
        return {"messages": [{"id": "wamid-out"}]}

    monkeypatch.setattr(flow_engine.ConsentFlow, "handle", fake_handle)
    monkeypatch.setattr(whatsapp_webhook, "send_text", fake_send_text)
    body = live_like_webhook_body()

    response = await webhook_client.post(
        "/webhooks/whatsapp",
        content=body,
        headers=signed_headers(body),
    )

    message = (
        await db_session.execute(select(Message).where(Message.wa_message_id == "wamid-live-1"))
    ).scalar_one()

    assert response.status_code == 200
    assert message.clinic_id == clinic_id
    assert message.direction == "inbound"
    assert message.content == "Hi"
    assert sent_messages == ["Consent prompt"]


@pytest.mark.asyncio
async def test_status_webhook_is_ignored_without_error(
    db_session: AsyncSession,
    webhook_client: httpx.AsyncClient,
    redis_client: Redis,
) -> None:
    await create_clinic(db_session)
    body = status_webhook_body()

    response = await webhook_client.post(
        "/webhooks/whatsapp",
        content=body,
        headers=signed_headers(body),
    )

    message_count = (
        await db_session.execute(select(func.count()).select_from(Message))
    ).scalar_one()
    failed_count = (
        await db_session.execute(select(func.count()).select_from(FailedMessage))
    ).scalar_one()

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert message_count == 0
    assert failed_count == 0


@pytest.mark.asyncio
async def test_consented_patient_routes_to_booking_flow_using_existing_session(
    db_session: AsyncSession,
    webhook_client: httpx.AsyncClient,
    redis_client: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clinic = await create_clinic(db_session)
    clinic_id = clinic.id
    session = await create_consented_patient_session(db_session, clinic)
    db_session.add(Test(clinic_id=clinic_id, name="CBC", category="Blood", sort_order=1))
    await db_session.commit()
    sent_messages: list[str] = []

    async def fake_send_text(
        _phone_number_id: str,
        _to: str,
        _access_token: str,
        body: str,
    ) -> dict[str, object]:
        sent_messages.append(body)
        return {"messages": [{"id": "wamid-out"}]}

    monkeypatch.setattr(whatsapp_webhook, "send_text", fake_send_text)
    body = webhook_body(message_id="wamid-booking", text="book blood test")

    response = await webhook_client.post(
        "/webhooks/whatsapp",
        content=body,
        headers=signed_headers(body),
    )

    sessions = (
        await db_session.execute(
            select(ConversationSession).where(ConversationSession.clinic_id == clinic_id),
        )
    ).scalars().all()

    assert response.status_code == 200
    assert sessions == [session]
    assert session.flow == "test_booking"
    assert session.is_active is True
    assert sent_messages == [render_category_prompt(["Blood"])]


@pytest.mark.parametrize(
    ("text", "flow_class"),
    [
        ("home collection", flow_engine.HomeCollectionFlow),
        ("check report", flow_engine.ReportInquiryFlow),
        ("cancel test", flow_engine.CancellationFlow),
    ],
)
@pytest.mark.asyncio
async def test_consented_patient_routes_remaining_diagnostics_intents(
    db_session: AsyncSession,
    webhook_client: httpx.AsyncClient,
    redis_client: Redis,
    monkeypatch: pytest.MonkeyPatch,
    text: str,
    flow_class: type[object],
) -> None:
    clinic = await create_clinic(db_session)
    await create_consented_patient_session(db_session, clinic)
    handled_messages: list[str] = []
    sent_messages: list[str] = []

    async def fake_handle(
        _flow: object,
        _session: ConversationSession | None,
        message: FlowMessage,
        _db: AsyncSession,
    ) -> str:
        handled_messages.append(message.text)
        return "routed"

    async def fake_send_text(
        _phone_number_id: str,
        _to: str,
        _access_token: str,
        body: str,
    ) -> dict[str, object]:
        sent_messages.append(body)
        return {"messages": [{"id": "wamid-out"}]}

    monkeypatch.setattr(flow_class, "handle", fake_handle)
    monkeypatch.setattr(whatsapp_webhook, "send_text", fake_send_text)
    body = webhook_body(message_id=f"wamid-{text}", text=text)

    response = await webhook_client.post(
        "/webhooks/whatsapp",
        content=body,
        headers=signed_headers(body),
    )

    assert response.status_code == 200
    assert handled_messages == [text]
    assert sent_messages == ["routed"]


@pytest.mark.asyncio
async def test_owner_message_routes_to_admin_flow_without_patient_consent(
    db_session: AsyncSession,
    webhook_client: httpx.AsyncClient,
    redis_client: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clinic = await create_clinic(db_session)
    sent_messages: list[str] = []

    async def fake_send_text(
        _phone_number_id: str,
        _to: str,
        _access_token: str,
        body: str,
    ) -> dict[str, object]:
        sent_messages.append(body)
        return {"messages": [{"id": "wamid-out"}]}

    monkeypatch.setattr(whatsapp_webhook, "send_text", fake_send_text)
    body = webhook_body(
        message_id="wamid-owner",
        text="not a known command",
        whatsapp_number=clinic.owner_whatsapp,
    )

    response = await webhook_client.post(
        "/webhooks/whatsapp",
        content=body,
        headers=signed_headers(body),
    )

    assert response.status_code == 200
    assert sent_messages == [ADMIN_UNKNOWN_COMMAND]


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

    monkeypatch.setattr(flow_engine.ConsentFlow, "handle", failing_handle)
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
