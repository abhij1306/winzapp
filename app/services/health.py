from __future__ import annotations

from typing import Literal

from redis.asyncio import Redis
from sqlalchemy import text

from app.config import get_settings
from app.database import SessionLocal

HealthCheck = Literal["ok", "error"]


async def get_health_status() -> dict[str, object]:
    checks = {
        "database": await check_database(),
        "redis": await check_redis(),
    }
    return {
        "status": "ok" if all(value == "ok" for value in checks.values()) else "degraded",
        "checks": checks,
    }


async def check_database() -> HealthCheck:
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        return "error"
    return "ok"


async def check_redis() -> HealthCheck:
    client = Redis.from_url(get_settings().redis_url, decode_responses=True)
    try:
        await client.ping()
    except Exception:
        return "error"
    finally:
        await client.aclose()
    return "ok"
