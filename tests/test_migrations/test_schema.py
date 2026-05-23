from collections.abc import Iterator
from uuid import uuid4

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import get_settings

EXPECTED_TABLES = {
    "alembic_version",
    "clinics",
    "doctors",
    "patients",
    "appointment_slots",
    "appointments",
    "tests",
    "test_bookings",
    "conversation_sessions",
    "messages",
    "failed_messages",
    "audit_log",
    "recall_schedules",
    "reviews",
    "broadcasts",
}


@pytest.fixture(scope="module", autouse=True)
def migrated_database() -> Iterator[None]:
    command.upgrade(Config("alembic.ini"), "head")
    yield


@pytest_asyncio.fixture
async def migration_engine() -> AsyncEngine:
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        yield engine
    finally:
        await engine.dispose()


async def get_table_names(engine: AsyncEngine) -> set[str]:
    async with engine.connect() as connection:
        return await connection.run_sync(
            lambda sync_connection: set(inspect(sync_connection).get_table_names()),
        )


async def get_unique_constraints(engine: AsyncEngine, table_name: str) -> list[set[str]]:
    async with engine.connect() as connection:
        constraints = await connection.run_sync(
            lambda sync_connection: inspect(sync_connection).get_unique_constraints(table_name),
        )
    return [{column for column in constraint["column_names"]} for constraint in constraints]


@pytest.mark.asyncio
async def test_initial_migration_creates_expected_tables(migration_engine: AsyncEngine) -> None:
    table_names = await get_table_names(migration_engine)

    assert EXPECTED_TABLES.issubset(table_names)


@pytest.mark.asyncio
async def test_messages_has_unique_wa_message_id(migration_engine: AsyncEngine) -> None:
    unique_constraints = await get_unique_constraints(migration_engine, "messages")

    assert {"wa_message_id"} in unique_constraints


@pytest.mark.asyncio
async def test_patients_has_unique_clinic_whatsapp(migration_engine: AsyncEngine) -> None:
    unique_constraints = await get_unique_constraints(migration_engine, "patients")

    assert {"clinic_id", "whatsapp_number"} in unique_constraints


@pytest.mark.asyncio
async def test_patient_rls_policy_hides_other_clinic_rows(migration_engine: AsyncEngine) -> None:
    first_clinic_id = str(uuid4())
    second_clinic_id = str(uuid4())
    role_name = f"rls_reader_{uuid4().hex}"

    async with migration_engine.connect() as connection:
        transaction = await connection.begin()
        try:
            await connection.execute(text(f'CREATE ROLE "{role_name}" NOLOGIN'))
            for clinic_id, phone in (
                (first_clinic_id, "+919100000001"),
                (second_clinic_id, "+919100000002"),
            ):
                await connection.execute(
                    text(
                        "INSERT INTO clinics "
                        "(id, name, whatsapp_number, owner_whatsapp, timezone, plan, "
                        "plan_active, settings) "
                        "VALUES (:clinic_id, 'RLS Clinic', :phone, :phone, "
                        "'Asia/Kolkata', 'diagnostic', true, '{}'::jsonb)",
                    ),
                    {"clinic_id": clinic_id, "phone": phone},
                )
                await connection.execute(
                    text(
                        "INSERT INTO patients (clinic_id, whatsapp_number, opt_in, tags) "
                        "VALUES (:clinic_id, :phone, true, ARRAY[]::text[])",
                    ),
                    {"clinic_id": clinic_id, "phone": phone},
                )

            await connection.execute(text(f'GRANT USAGE ON SCHEMA public TO "{role_name}"'))
            await connection.execute(text(f'GRANT SELECT ON patients TO "{role_name}"'))
            await connection.execute(text(f'SET LOCAL ROLE "{role_name}"'))
            await connection.execute(
                text("SELECT set_config('app.clinic_id', :clinic_id, true)"),
                {"clinic_id": first_clinic_id},
            )

            phones = (
                await connection.execute(
                    text("SELECT whatsapp_number FROM patients ORDER BY whatsapp_number"),
                )
            ).scalars().all()

            assert phones == ["+919100000001"]
        finally:
            await connection.execute(text("RESET ROLE"))
            await transaction.rollback()
