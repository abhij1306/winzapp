from uuid import uuid4

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Clinic, Test
from app.services.cache import (
    CLINIC_CACHE_TTL_SECONDS,
    TESTS_CACHE_TTL_SECONDS,
    catalog_cache_key,
    clinic_cache_key,
    get_clinic_cached,
    get_session_cached,
    get_tests_cached,
    invalidate_clinic_cache,
    invalidate_tests_cache,
    update_session_cache,
)


@pytest_asyncio.fixture
async def redis_client() -> Redis:
    client = Redis.from_url(get_settings().redis_url, decode_responses=True)
    await client.flushdb()
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()


@pytest.mark.asyncio
async def test_clinic_cache_miss_reads_db_and_writes_redis(
    db_session: AsyncSession,
    redis_client: Redis,
) -> None:
    phone_number_id = "phone-123"
    clinic = Clinic(
        id=uuid4(),
        name="Demo Lab",
        whatsapp_number="+919999999999",
        owner_whatsapp="+918888888888",
        settings={"wa_phone_number_id": phone_number_id},
    )
    db_session.add(clinic)
    await db_session.commit()

    result = await get_clinic_cached(phone_number_id, db_session)

    assert result is not None
    assert result["name"] == "Demo Lab"
    assert await redis_client.exists(clinic_cache_key(phone_number_id)) == 1
    assert await redis_client.ttl(clinic_cache_key(phone_number_id)) <= CLINIC_CACHE_TTL_SECONDS


@pytest.mark.asyncio
async def test_cache_hit_does_not_read_db(redis_client: Redis) -> None:
    phone_number_id = "phone-hit"
    await redis_client.setex(
        clinic_cache_key(phone_number_id),
        CLINIC_CACHE_TTL_SECONDS,
        '{"id":"clinic-1","name":"Cached Lab"}',
    )

    class ExplodingDb:
        async def execute(self, *_args: object, **_kwargs: object) -> None:
            raise AssertionError("DB should not be read on cache hit")

    result = await get_clinic_cached(phone_number_id, ExplodingDb())  # type: ignore[arg-type]

    assert result == {"id": "clinic-1", "name": "Cached Lab"}


@pytest.mark.asyncio
async def test_tests_cache_miss_reads_db_and_sets_ttl(
    db_session: AsyncSession,
    redis_client: Redis,
) -> None:
    clinic_id = uuid4()
    db_session.add(
        Clinic(
            id=clinic_id,
            name="Demo Lab",
            whatsapp_number="+919999999991",
            owner_whatsapp="+918888888881",
            settings={},
        ),
    )
    db_session.add(Test(clinic_id=clinic_id, name="CBC", sort_order=1))
    await db_session.commit()

    result = await get_tests_cached(str(clinic_id), db_session)

    assert [item["name"] for item in result] == ["CBC"]
    assert await redis_client.ttl(catalog_cache_key(str(clinic_id))) <= TESTS_CACHE_TTL_SECONDS


@pytest.mark.asyncio
async def test_session_cache_update_and_read(redis_client: Redis, db_session: AsyncSession) -> None:
    clinic_id = str(uuid4())
    whatsapp_number = "+919999999999"
    session = {"clinic_id": clinic_id, "whatsapp_number": whatsapp_number, "flow": "test_booking"}

    await update_session_cache(whatsapp_number, clinic_id, session)
    result = await get_session_cached(whatsapp_number, clinic_id, db_session)

    assert result == session


@pytest.mark.asyncio
async def test_invalidate_deletes_keys(redis_client: Redis) -> None:
    phone_number_id = "phone-delete"
    clinic_id = str(uuid4())
    await redis_client.setex(clinic_cache_key(phone_number_id), CLINIC_CACHE_TTL_SECONDS, "{}")
    await redis_client.setex(catalog_cache_key(clinic_id), TESTS_CACHE_TTL_SECONDS, "[]")

    await invalidate_clinic_cache(phone_number_id)
    await invalidate_tests_cache(clinic_id)

    assert await redis_client.exists(clinic_cache_key(phone_number_id)) == 0
    assert await redis_client.exists(catalog_cache_key(clinic_id)) == 0
