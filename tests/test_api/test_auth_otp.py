from __future__ import annotations

from collections.abc import AsyncGenerator
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.main import app
from app.models import Clinic
from app.services.auth import decode_access_token, otp_cache_key


@pytest_asyncio.fixture
async def redis_client() -> AsyncGenerator[Redis, None]:
    client = Redis.from_url(get_settings().redis_url, decode_responses=True)
    await client.flushdb()
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()


@pytest_asyncio.fixture
async def api_client(db_session: AsyncSession) -> AsyncGenerator[httpx.AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def create_owner_clinic(
    db_session: AsyncSession,
    owner_whatsapp: str,
) -> Clinic:
    clinic = Clinic(
        id=uuid4(),
        name="Demo Diagnostics",
        whatsapp_number="+919000000001",
        owner_whatsapp=owner_whatsapp,
        clinic_type="diagnostic",
        settings={"wa_phone_number_id": "phone-number-id"},
    )
    db_session.add(clinic)
    await db_session.commit()
    return clinic


@pytest.mark.asyncio
async def test_send_otp_stores_code_and_sends_whatsapp_message(
    db_session: AsyncSession,
    redis_client: Redis,
    api_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clinic = await create_owner_clinic(db_session, "+919000000002")
    sent_messages = []

    async def fake_send_text(
        phone_number_id: str,
        to: str,
        access_token: str,
        body: str,
    ) -> dict[str, object]:
        sent_messages.append(
            {
                "phone_number_id": phone_number_id,
                "to": to,
                "body": body,
            },
        )
        return {"messages": [{"id": "wamid.otp"}]}

    monkeypatch.setattr("app.services.auth.generate_otp", lambda: "123456")
    monkeypatch.setattr("app.services.whatsapp_sender.send_text", fake_send_text)

    response = await api_client.post(
        "/api/v1/auth/otp/send",
        json={"owner_whatsapp": clinic.owner_whatsapp},
    )

    cached = await redis_client.get(otp_cache_key(clinic.owner_whatsapp))
    ttl = await redis_client.ttl(otp_cache_key(clinic.owner_whatsapp))

    assert response.status_code == 200
    assert response.json() == {"data": {"status": "otp_sent"}}
    assert cached is not None
    assert "123456" not in cached
    assert ttl > 0
    assert sent_messages == [
        {
            "phone_number_id": "phone-number-id",
            "to": clinic.owner_whatsapp,
            "body": "Aapka Winzapp login OTP 123456 hai. Ye 5 minutes ke liye valid hai.",
        },
    ]


@pytest.mark.asyncio
async def test_send_otp_unknown_owner_returns_error_envelope(
    redis_client: Redis,
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.post(
        "/api/v1/auth/otp/send",
        json={"owner_whatsapp": "+919000000003"},
    )

    body = response.json()

    assert response.status_code == 404
    assert body["error"]["code"] == "OWNER_NOT_FOUND"
    assert body["error"]["message"] == "Owner WhatsApp number was not found."
    assert body["error"]["request_id"]


@pytest.mark.asyncio
async def test_verify_otp_returns_short_lived_bearer_token(
    db_session: AsyncSession,
    redis_client: Redis,
    api_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clinic = await create_owner_clinic(db_session, "+919000000004")

    async def fake_send_text(
        phone_number_id: str,
        to: str,
        access_token: str,
        body: str,
    ) -> dict[str, object]:
        return {"messages": [{"id": "wamid.otp"}]}

    monkeypatch.setattr("app.services.auth.generate_otp", lambda: "654321")
    monkeypatch.setattr("app.services.whatsapp_sender.send_text", fake_send_text)
    await api_client.post("/api/v1/auth/otp/send", json={"owner_whatsapp": clinic.owner_whatsapp})

    response = await api_client.post(
        "/api/v1/auth/otp/verify",
        json={"owner_whatsapp": clinic.owner_whatsapp, "otp": "654321"},
    )

    body = response.json()["data"]
    claims = decode_access_token(body["access_token"])
    cached_after_verify = await redis_client.get(otp_cache_key(clinic.owner_whatsapp))

    assert response.status_code == 200
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == get_settings().jwt_access_token_minutes * 60
    assert claims["sub"] == clinic.owner_whatsapp
    assert claims["clinic_id"] == str(clinic.id)
    assert claims["role"] == "owner"
    assert cached_after_verify is None


@pytest.mark.asyncio
async def test_verify_otp_invalid_code_returns_error_envelope(
    db_session: AsyncSession,
    redis_client: Redis,
    api_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clinic = await create_owner_clinic(db_session, "+919000000005")

    async def fake_send_text(
        phone_number_id: str,
        to: str,
        access_token: str,
        body: str,
    ) -> dict[str, object]:
        return {"messages": [{"id": "wamid.otp"}]}

    monkeypatch.setattr("app.services.auth.generate_otp", lambda: "111111")
    monkeypatch.setattr("app.services.whatsapp_sender.send_text", fake_send_text)
    await api_client.post("/api/v1/auth/otp/send", json={"owner_whatsapp": clinic.owner_whatsapp})

    response = await api_client.post(
        "/api/v1/auth/otp/verify",
        json={"owner_whatsapp": clinic.owner_whatsapp, "otp": "222222"},
    )

    body = response.json()

    assert response.status_code == 401
    assert body["error"]["code"] == "INVALID_OTP"
    assert body["error"]["message"] == "OTP is invalid or expired."
    assert body["error"]["request_id"]
