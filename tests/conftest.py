from collections.abc import AsyncGenerator, Generator
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.main import app
from app.models import Base


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    settings = get_settings()
    admin_engine = create_async_engine(settings.test_database_url, pool_pre_ping=True)
    schema_name = f"test_{uuid4().hex}"

    async with admin_engine.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))

    engine = create_async_engine(
        settings.test_database_url,
        pool_pre_ping=True,
        connect_args={"server_settings": {"search_path": f"{schema_name},public"}},
    )
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(lambda sync_connection: Base.metadata.create_all(
            sync_connection,
            checkfirst=False,
        ))

    try:
        async with session_factory() as session:
            await session.execute(text(f'SET search_path TO "{schema_name}", public'))
            yield session
            await session.rollback()
    finally:
        async with admin_engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
        await engine.dispose()
        await admin_engine.dispose()
