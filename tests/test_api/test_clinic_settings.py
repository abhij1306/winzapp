from __future__ import annotations

from collections.abc import AsyncGenerator
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.main import app
from app.models import AuditLog, Clinic
from app.services.auth import create_access_token
from app.services.cache import clinic_cache_key, clinic_id_cache_key


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


async def create_clinic(
    db_session: AsyncSession,
    owner_whatsapp: str,
    phone_number_id: str = "phone-number-id",
) -> Clinic:
    clinic_suffix = owner_whatsapp[-4:]
    clinic = Clinic(
        id=uuid4(),
        name="Demo Diagnostics",
        owner_name="Owner",
        whatsapp_number=f"+91800000{clinic_suffix}",
        owner_whatsapp=owner_whatsapp,
        clinic_type="diagnostic",
        address="MG Road",
        city="Bhopal",
        pincode="462001",
        timezone="Asia/Kolkata",
        plan="diagnostic",
        settings={
            "wa_phone_number_id": phone_number_id,
            "features": {"home_collection": True, "recall_automation": True},
        },
    )
    db_session.add(clinic)
    await db_session.commit()
    return clinic


def auth_headers(clinic: Clinic) -> dict[str, str]:
    token = create_access_token(clinic.owner_whatsapp, str(clinic.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_get_clinic_settings_returns_owner_clinic(
    db_session: AsyncSession,
    redis_client: Redis,
    api_client: httpx.AsyncClient,
) -> None:
    clinic = await create_clinic(db_session, "+919000000002")

    response = await api_client.get(
        f"/api/v1/clinics/{clinic.id}",
        headers=auth_headers(clinic),
    )

    assert response.status_code == 200
    assert response.json()["data"] == {
        "id": str(clinic.id),
        "name": "Demo Diagnostics",
        "owner_name": "Owner",
        "clinic_type": "diagnostic",
        "whatsapp_number": clinic.whatsapp_number,
        "owner_whatsapp": "+919000000002",
        "address": "MG Road",
        "city": "Bhopal",
        "pincode": "462001",
        "timezone": "Asia/Kolkata",
        "plan": "diagnostic",
        "plan_active": True,
        "settings": {
            "wa_phone_number_id": "phone-number-id",
            "features": {"home_collection": True, "recall_automation": True},
        },
    }


@pytest.mark.asyncio
async def test_get_clinic_settings_rejects_missing_token(
    redis_client: Redis,
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.get(f"/api/v1/clinics/{uuid4()}")

    body = response.json()

    assert response.status_code == 401
    assert body["error"]["code"] == "AUTH_REQUIRED"
    assert body["error"]["message"] == "Bearer token is required."
    assert body["error"]["request_id"]


@pytest.mark.asyncio
async def test_get_clinic_settings_rejects_cross_clinic_access(
    db_session: AsyncSession,
    redis_client: Redis,
    api_client: httpx.AsyncClient,
) -> None:
    owner_clinic = await create_clinic(db_session, "+919000000003")
    other_clinic = await create_clinic(db_session, "+919000000004", "other-phone-id")

    response = await api_client.get(
        f"/api/v1/clinics/{other_clinic.id}",
        headers=auth_headers(owner_clinic),
    )

    body = response.json()

    assert response.status_code == 403
    assert body["error"]["code"] == "CLINIC_FORBIDDEN"
    assert body["error"]["message"] == "Token does not allow access to this clinic."


@pytest.mark.asyncio
async def test_update_clinic_settings_invalidates_cache_and_writes_audit(
    db_session: AsyncSession,
    redis_client: Redis,
    api_client: httpx.AsyncClient,
) -> None:
    clinic = await create_clinic(db_session, "+919000000005")
    await redis_client.set(clinic_id_cache_key(str(clinic.id)), "{}")
    await redis_client.set(clinic_cache_key("phone-number-id"), "{}")

    response = await api_client.put(
        f"/api/v1/clinics/{clinic.id}",
        headers=auth_headers(clinic),
        json={
            "name": "Updated Diagnostics",
            "owner_name": "Updated Owner",
            "address": "12 Lake Road",
            "city": "Indore",
            "pincode": "452001",
            "gbp_review_link": "https://maps.example/review",
            "settings": {
                "wa_phone_number_id": "new-phone-id",
                "features": {"home_collection": False, "recall_automation": True},
            },
        },
    )

    refreshed = (
        await db_session.execute(select(Clinic).where(Clinic.id == clinic.id))
    ).scalar_one()
    audit = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.clinic_id == clinic.id,
                AuditLog.action == "clinic.updated",
            ),
        )
    ).scalar_one()

    assert response.status_code == 200
    assert response.json()["data"]["name"] == "Updated Diagnostics"
    assert refreshed.name == "Updated Diagnostics"
    assert refreshed.city == "Indore"
    assert refreshed.settings == {
        "wa_phone_number_id": "new-phone-id",
        "features": {"home_collection": False, "recall_automation": True},
    }
    assert await redis_client.get(clinic_id_cache_key(str(clinic.id))) is None
    assert await redis_client.get(clinic_cache_key("phone-number-id")) is None
    assert audit.entity_id == clinic.id
    assert audit.actor_type == "owner"
    assert audit.diff["before"]["name"] == "Demo Diagnostics"
    assert audit.diff["after"]["name"] == "Updated Diagnostics"
