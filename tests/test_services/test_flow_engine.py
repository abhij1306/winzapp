from uuid import uuid4

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.flows.base_flow import FlowMessage
from app.models import Clinic, ConversationSession, Patient, Test
from app.services.cache import get_session_cached
from app.services.flow_engine import handle_flow_message
from app.templates.hinglish import render_category_prompt, render_main_menu
from app.utils.datetime_utils import now_ist


@pytest_asyncio.fixture
async def redis_client() -> Redis:
    client = Redis.from_url(get_settings().redis_url, decode_responses=True)
    await client.flushdb()
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()


async def create_menu_fixture(db_session: AsyncSession) -> tuple[object, Patient]:
    clinic_id = uuid4()
    patient = Patient(
        id=uuid4(),
        clinic_id=clinic_id,
        whatsapp_number="918999635679",
        opt_in=True,
        opt_in_at=now_ist(),
    )
    db_session.add(
        Clinic(
            id=clinic_id,
            name="Demo Diagnostics",
            whatsapp_number="+919000000001",
            owner_whatsapp="+919000000002",
            clinic_type="diagnostic",
            settings={},
        ),
    )
    db_session.add_all(
        [
            patient,
            Test(id=uuid4(), clinic_id=clinic_id, name="CBC", category="Blood", sort_order=1),
            Test(
                id=uuid4(),
                clinic_id=clinic_id,
                name="Thyroid Profile",
                category="Hormone",
                sort_order=2,
            ),
        ],
    )
    await db_session.commit()
    return clinic_id, patient


@pytest.mark.asyncio
async def test_main_menu_number_routes_to_test_booking_flow(
    db_session: AsyncSession,
    redis_client: Redis,
) -> None:
    clinic_id, patient = await create_menu_fixture(db_session)

    response = await handle_flow_message(
        session=None,
        message=FlowMessage(clinic_id=clinic_id, whatsapp_number=patient.whatsapp_number, text="1"),
        clinic={"owner_whatsapp": "+919000000002"},
        db=db_session,
    )

    session = (
        await db_session.execute(
            select(ConversationSession).where(
                ConversationSession.clinic_id == clinic_id,
                ConversationSession.whatsapp_number == patient.whatsapp_number,
                ConversationSession.is_active.is_(True),
            ),
        )
    ).scalar_one()

    assert response == render_category_prompt(["Blood", "Hormone"])
    assert session.flow == "test_booking"
    assert session.step == "select_category"


@pytest.mark.asyncio
async def test_main_menu_request_resets_active_session(
    db_session: AsyncSession,
    redis_client: Redis,
) -> None:
    clinic_id, patient = await create_menu_fixture(db_session)
    session = ConversationSession(
        clinic_id=clinic_id,
        patient_id=patient.id,
        whatsapp_number=patient.whatsapp_number,
        flow="test_booking",
        step="select_test",
        context={"category": "Blood"},
        is_active=True,
    )
    db_session.add(session)
    await db_session.commit()

    response = await handle_flow_message(
        session=session,
        message=FlowMessage(clinic_id=clinic_id, whatsapp_number=patient.whatsapp_number, text="0"),
        clinic={"owner_whatsapp": "+919000000002"},
        db=db_session,
    )

    cached = await get_session_cached(patient.whatsapp_number, str(clinic_id), db_session)

    assert response == render_main_menu()
    assert session.is_active is False
    assert cached is not None
    assert cached["is_active"] is False
