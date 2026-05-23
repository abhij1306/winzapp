from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Clinic, ConversationSession, Test

CLINIC_CACHE_TTL_SECONDS = 60 * 60
TESTS_CACHE_TTL_SECONDS = 60 * 60
SESSION_CACHE_TTL_SECONDS = 30 * 60


def clinic_cache_key(phone_number_id: str) -> str:
    return f"clinic:{phone_number_id}"


def clinic_id_cache_key(clinic_id: str) -> str:
    return f"clinic-id:{clinic_id}"


def catalog_cache_key(clinic_id: str) -> str:
    return f"tests:{clinic_id}"


def session_cache_key(whatsapp_number: str, clinic_id: str) -> str:
    return f"session:{clinic_id}:{whatsapp_number}"


def get_redis_client() -> Redis:
    return cast(Redis, Redis.from_url(get_settings().redis_url, decode_responses=True))


def json_default(value: object) -> str:
    if isinstance(value, UUID | datetime | date | Decimal):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def dumps_json(value: object) -> str:
    return json.dumps(value, default=json_default, separators=(",", ":"))


def loads_dict(value: str) -> dict[str, object]:
    return cast(dict[str, object], json.loads(value))


def loads_list(value: str) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], json.loads(value))


async def redis_get(key: str) -> str | None:
    client = get_redis_client()
    try:
        value = await client.get(key)
    except (OSError, RedisError):
        return None
    finally:
        await client.aclose()
    return cast(str | None, value)


async def redis_set_json(key: str, ttl_seconds: int, value: object) -> None:
    client = get_redis_client()
    try:
        await client.setex(key, ttl_seconds, dumps_json(value))
    except (OSError, RedisError):
        return
    finally:
        await client.aclose()


async def redis_delete(key: str) -> None:
    client = get_redis_client()
    try:
        await client.delete(key)
    except (OSError, RedisError):
        return
    finally:
        await client.aclose()


def clinic_to_dict(clinic: Clinic) -> dict[str, object]:
    return {
        "id": str(clinic.id),
        "name": clinic.name,
        "clinic_type": clinic.clinic_type,
        "whatsapp_number": clinic.whatsapp_number,
        "owner_whatsapp": clinic.owner_whatsapp,
        "city": clinic.city,
        "timezone": clinic.timezone,
        "plan": clinic.plan,
        "plan_active": clinic.plan_active,
        "settings": clinic.settings,
    }


def test_to_dict(test: Test) -> dict[str, object]:
    return {
        "id": str(test.id),
        "clinic_id": str(test.clinic_id),
        "name": test.name,
        "price": str(test.price) if test.price is not None else None,
        "duration_hours": test.duration_hours,
        "requires_fasting": test.requires_fasting,
        "home_collection_available": test.home_collection_available,
        "category": test.category,
        "sort_order": test.sort_order,
    }


def session_to_dict(session: ConversationSession) -> dict[str, object]:
    return {
        "id": str(session.id),
        "clinic_id": str(session.clinic_id),
        "patient_id": str(session.patient_id) if session.patient_id else None,
        "whatsapp_number": session.whatsapp_number,
        "flow": session.flow,
        "step": session.step,
        "context": session.context,
        "is_active": session.is_active,
    }


async def get_clinic_cached(
    phone_number_id: str,
    db: AsyncSession,
) -> dict[str, object] | None:
    key = clinic_cache_key(phone_number_id)
    cached = await redis_get(key)
    if cached is not None:
        return loads_dict(cached)

    statement = select(Clinic).where(
        Clinic.settings["wa_phone_number_id"].as_string() == phone_number_id,
        Clinic.deleted_at.is_(None),
    )
    clinic = (await db.execute(statement)).scalar_one_or_none()
    if clinic is None:
        return None

    result = clinic_to_dict(clinic)
    await redis_set_json(key, CLINIC_CACHE_TTL_SECONDS, result)
    return result


async def get_clinic_by_id_cached(
    clinic_id: str,
    db: AsyncSession,
) -> dict[str, object] | None:
    key = clinic_id_cache_key(clinic_id)
    cached = await redis_get(key)
    if cached is not None:
        return loads_dict(cached)

    statement = select(Clinic).where(Clinic.id == clinic_id, Clinic.deleted_at.is_(None))
    clinic = (await db.execute(statement)).scalar_one_or_none()
    if clinic is None:
        return None

    result = clinic_to_dict(clinic)
    await redis_set_json(key, CLINIC_CACHE_TTL_SECONDS, result)
    return result


async def get_tests_cached(clinic_id: str, db: AsyncSession) -> list[dict[str, object]]:
    key = catalog_cache_key(clinic_id)
    cached = await redis_get(key)
    if cached is not None:
        return loads_list(cached)

    statement = (
        select(Test)
        .where(Test.clinic_id == clinic_id, Test.deleted_at.is_(None), Test.is_active.is_(True))
        .order_by(Test.sort_order, Test.name)
    )
    rows = (await db.execute(statement)).scalars().all()
    result = [test_to_dict(row) for row in rows]
    await redis_set_json(key, TESTS_CACHE_TTL_SECONDS, result)
    return result


async def get_session_cached(
    whatsapp_number: str,
    clinic_id: str,
    db: AsyncSession,
) -> dict[str, object] | None:
    key = session_cache_key(whatsapp_number, clinic_id)
    cached = await redis_get(key)
    if cached is not None:
        return loads_dict(cached)

    statement = select(ConversationSession).where(
        ConversationSession.clinic_id == clinic_id,
        ConversationSession.whatsapp_number == whatsapp_number,
        ConversationSession.is_active.is_(True),
    )
    session = (await db.execute(statement)).scalar_one_or_none()
    if session is None:
        return None

    result = session_to_dict(session)
    await redis_set_json(key, SESSION_CACHE_TTL_SECONDS, result)
    return result


async def update_session_cache(
    whatsapp_number: str,
    clinic_id: str,
    session_dict: dict[str, object],
) -> None:
    await redis_set_json(
        session_cache_key(whatsapp_number, clinic_id),
        SESSION_CACHE_TTL_SECONDS,
        session_dict,
    )


async def invalidate_clinic_cache(phone_number_id: str) -> None:
    await redis_delete(clinic_cache_key(phone_number_id))


async def invalidate_tests_cache(clinic_id: str) -> None:
    await redis_delete(catalog_cache_key(clinic_id))
