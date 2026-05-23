from __future__ import annotations

from collections.abc import AsyncGenerator
from decimal import Decimal
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
from app.models import AuditLog, Clinic, Test
from app.services.auth import create_access_token
from app.services.cache import catalog_cache_key


@pytest_asyncio.fixture
async def api_client(db_session: AsyncSession) -> AsyncGenerator[httpx.AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def redis_client() -> AsyncGenerator[Redis, None]:
    client = Redis.from_url(get_settings().redis_url, decode_responses=True)
    await client.flushdb()
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()


async def create_test_catalog_fixture(
    db_session: AsyncSession,
    owner_whatsapp: str = "+919000004001",
) -> tuple[Clinic, Test]:
    suffix = owner_whatsapp[-4:]
    clinic = Clinic(
        id=uuid4(),
        name="Catalog Diagnostics",
        owner_name="Owner",
        whatsapp_number=f"+91810000{suffix}",
        owner_whatsapp=owner_whatsapp,
        clinic_type="diagnostic",
        settings={"wa_phone_number_id": f"phone-catalog-{suffix}"},
    )
    test = Test(
        clinic_id=clinic.id,
        name="CBC",
        name_hindi="CBC",
        description="Complete blood count",
        price=Decimal("300.00"),
        duration_hours=4,
        requires_fasting=False,
        home_collection_available=True,
        category="Blood",
        is_active=True,
        sort_order=2,
    )
    db_session.add_all([clinic, test])
    await db_session.commit()
    return clinic, test


def auth_headers(clinic: Clinic) -> dict[str, str]:
    token = create_access_token(clinic.owner_whatsapp, str(clinic.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_list_tests_filters_by_clinic_and_active_flag(
    db_session: AsyncSession,
    api_client: httpx.AsyncClient,
) -> None:
    clinic, test = await create_test_catalog_fixture(db_session)
    await create_test_catalog_fixture(db_session, "+919000004002")
    db_session.add(
        Test(
            clinic_id=clinic.id,
            name="Old Test",
            price=Decimal("100.00"),
            is_active=False,
            sort_order=1,
        ),
    )
    await db_session.commit()

    response = await api_client.get(
        f"/api/v1/clinics/{clinic.id}/tests",
        headers=auth_headers(clinic),
        params={"active": "true"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] == 1
    assert body["data"][0] == {
        "id": str(test.id),
        "name": "CBC",
        "name_hindi": "CBC",
        "description": "Complete blood count",
        "price": "300.00",
        "duration_hours": 4,
        "requires_fasting": False,
        "home_collection_available": True,
        "category": "Blood",
        "is_active": True,
        "sort_order": 2,
    }


@pytest.mark.asyncio
async def test_create_test_invalidates_catalog_cache_and_writes_audit(
    db_session: AsyncSession,
    redis_client: Redis,
    api_client: httpx.AsyncClient,
) -> None:
    clinic, _test = await create_test_catalog_fixture(db_session)
    await redis_client.set(catalog_cache_key(str(clinic.id)), "[]")

    response = await api_client.post(
        f"/api/v1/clinics/{clinic.id}/tests",
        headers=auth_headers(clinic),
        json={
            "name": "Thyroid Profile",
            "price": "650.00",
            "duration_hours": 8,
            "requires_fasting": True,
            "home_collection_available": True,
            "category": "Thyroid",
            "sort_order": 3,
        },
    )

    assert response.status_code == 201

    body = response.json()
    created = (
        await db_session.execute(
            select(Test).where(Test.clinic_id == clinic.id, Test.id == body["data"]["id"]),
        )
    ).scalar_one()
    audit = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.clinic_id == clinic.id,
                AuditLog.action == "test.created",
                AuditLog.entity_id == created.id,
            ),
        )
    ).scalar_one()

    assert body["data"]["name"] == "Thyroid Profile"
    assert created.price == Decimal("650.00")
    assert await redis_client.get(catalog_cache_key(str(clinic.id))) is None
    assert audit.actor_type == "owner"


@pytest.mark.asyncio
async def test_update_test_invalidates_catalog_cache_and_writes_audit(
    db_session: AsyncSession,
    redis_client: Redis,
    api_client: httpx.AsyncClient,
) -> None:
    clinic, test = await create_test_catalog_fixture(db_session)
    await redis_client.set(catalog_cache_key(str(clinic.id)), "[]")

    response = await api_client.put(
        f"/api/v1/clinics/{clinic.id}/tests/{test.id}",
        headers=auth_headers(clinic),
        json={"price": "350.00", "is_active": False, "sort_order": 5},
    )

    assert response.status_code == 200

    refreshed = (
        await db_session.execute(
            select(Test).where(Test.clinic_id == clinic.id, Test.id == test.id),
        )
    ).scalar_one()
    audit = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.clinic_id == clinic.id,
                AuditLog.action == "test.updated",
                AuditLog.entity_id == test.id,
            ),
        )
    ).scalar_one()

    assert response.json()["data"]["price"] == "350.00"
    assert refreshed.is_active is False
    assert await redis_client.get(catalog_cache_key(str(clinic.id))) is None
    assert audit.diff["before"]["price"] == "300.00"
    assert audit.diff["after"]["price"] == "350.00"


@pytest.mark.asyncio
async def test_delete_test_soft_deletes_and_invalidates_catalog_cache(
    db_session: AsyncSession,
    redis_client: Redis,
    api_client: httpx.AsyncClient,
) -> None:
    clinic, test = await create_test_catalog_fixture(db_session)
    await redis_client.set(catalog_cache_key(str(clinic.id)), "[]")

    response = await api_client.delete(
        f"/api/v1/clinics/{clinic.id}/tests/{test.id}",
        headers=auth_headers(clinic),
    )

    assert response.status_code == 200

    refreshed = (
        await db_session.execute(
            select(Test).where(Test.clinic_id == clinic.id, Test.id == test.id),
        )
    ).scalar_one()
    audit = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.clinic_id == clinic.id,
                AuditLog.action == "test.deleted",
                AuditLog.entity_id == test.id,
            ),
        )
    ).scalar_one()

    assert response.json()["data"]["is_active"] is False
    assert refreshed.deleted_at is not None
    assert refreshed.is_active is False
    assert await redis_client.get(catalog_cache_key(str(clinic.id))) is None
    assert audit.actor_type == "owner"
