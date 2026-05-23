from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

settings = get_settings()

engine: AsyncEngine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await clear_tenant_context(session)


async def set_tenant_context(session: AsyncSession, clinic_id: str) -> None:
    await session.execute(
        text("SELECT set_config('app.clinic_id', :clinic_id, false)"),
        {"clinic_id": clinic_id},
    )


async def clear_tenant_context(session: AsyncSession) -> None:
    await session.rollback()
    await session.execute(text("RESET app.clinic_id"))
    await session.commit()
