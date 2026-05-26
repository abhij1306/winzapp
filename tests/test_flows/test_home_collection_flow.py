from decimal import Decimal
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi import HTTPException
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.flows.base_flow import FlowMessage
from app.flows.home_collection_flow import HomeCollectionFlow
from app.models import AuditLog, Clinic, ConversationSession, Patient, Test, TestBooking
from app.services.cache import get_session_cached
from app.templates.hinglish import (
    HOME_COLLECTION_CONFIRMED,
    render_address_prompt,
    render_home_test_selection_prompt,
    render_morning_slot_prompt,
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


async def create_home_collection_fixture(
    db_session: AsyncSession,
    clinic_id: UUID,
    whatsapp_number: str,
    home_collection_enabled: bool = True,
) -> tuple[Patient, Test, Test, ConversationSession]:
    db_session.add(
        Clinic(
            id=clinic_id,
            name="Demo Diagnostics",
            whatsapp_number="+919000000001",
            owner_whatsapp="+919000000002",
            clinic_type="diagnostic",
            settings={"features": {"home_collection": home_collection_enabled}},
        ),
    )
    patient = Patient(
        id=uuid4(),
        clinic_id=clinic_id,
        whatsapp_number=whatsapp_number,
        opt_in=True,
    )
    lipid = Test(
        id=uuid4(),
        clinic_id=clinic_id,
        name="Lipid Profile",
        category="Cardiac",
        price=Decimal("700.00"),
        sort_order=1,
        requires_fasting=True,
        home_collection_available=True,
    )
    urine = Test(
        id=uuid4(),
        clinic_id=clinic_id,
        name="Urine Routine",
        category="Urine",
        price=Decimal("150.00"),
        sort_order=2,
        requires_fasting=False,
        home_collection_available=False,
    )
    session = ConversationSession(
        clinic_id=clinic_id,
        patient_id=patient.id,
        whatsapp_number=whatsapp_number,
        flow="home_collection",
        step="select_test",
        context={},
    )
    db_session.add_all([patient, lipid, urine, session])
    await db_session.commit()
    return patient, lipid, urine, session


@pytest.mark.asyncio
async def test_home_collection_requires_enabled_feature_flag(
    db_session: AsyncSession,
    redis_client: Redis,
) -> None:
    clinic_id = uuid4()
    whatsapp_number = "+919999999990"
    _patient, _lipid, _urine, session = await create_home_collection_fixture(
        db_session,
        clinic_id,
        whatsapp_number,
        home_collection_enabled=False,
    )

    with pytest.raises(HTTPException) as exc_info:
        await HomeCollectionFlow().handle(
            session=session,
            message=FlowMessage(
                clinic_id=clinic_id,
                whatsapp_number=whatsapp_number,
                text="home collection chahiye",
            ),
            db=db_session,
        )

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_home_collection_starts_with_home_eligible_test_prompt(
    db_session: AsyncSession,
    redis_client: Redis,
) -> None:
    clinic_id = uuid4()
    whatsapp_number = "+919999999999"
    _patient, lipid, _urine, _session = await create_home_collection_fixture(
        db_session,
        clinic_id,
        whatsapp_number,
    )

    response = await HomeCollectionFlow().handle(
        session=None,
        message=FlowMessage(
            clinic_id=clinic_id,
            whatsapp_number=whatsapp_number,
            text="home collection chahiye",
        ),
        db=db_session,
    )

    session = (
        await db_session.execute(
            select(ConversationSession).where(
                ConversationSession.clinic_id == clinic_id,
                ConversationSession.whatsapp_number == whatsapp_number,
                ConversationSession.is_active.is_(True),
            ),
        )
    ).scalar_one()
    cached = await get_session_cached(whatsapp_number, str(clinic_id), db_session)

    assert response == render_home_test_selection_prompt(["Lipid Profile"])
    assert session.step == "select_test"
    assert session.context["available_test_ids"] == [str(lipid.id)]
    assert cached is not None
    assert cached["step"] == "select_test"


@pytest.mark.asyncio
async def test_home_collection_test_selection_captures_fasting_flag_and_asks_address(
    db_session: AsyncSession,
    redis_client: Redis,
) -> None:
    clinic_id = uuid4()
    whatsapp_number = "+919999999998"
    _patient, lipid, _urine, session = await create_home_collection_fixture(
        db_session,
        clinic_id,
        whatsapp_number,
    )
    session.context = {"available_test_ids": [str(lipid.id)]}
    await db_session.commit()

    response = await HomeCollectionFlow().handle(
        session=session,
        message=FlowMessage(
            clinic_id=clinic_id,
            whatsapp_number=whatsapp_number,
            text="1",
        ),
        db=db_session,
    )

    assert response == render_address_prompt(requires_fasting=True)
    assert session.step == "capture_address"
    assert session.context["selected_test_id"] == str(lipid.id)
    assert session.context["requires_fasting"] is True


@pytest.mark.asyncio
async def test_home_collection_address_prompts_morning_slot(
    db_session: AsyncSession,
    redis_client: Redis,
) -> None:
    clinic_id = uuid4()
    whatsapp_number = "+919999999997"
    _patient, lipid, _urine, session = await create_home_collection_fixture(
        db_session,
        clinic_id,
        whatsapp_number,
    )
    session.step = "capture_address"
    session.context = {
        "selected_test_id": str(lipid.id),
        "selected_test_name": "Lipid Profile",
        "selected_test_price": "700.00",
        "requires_fasting": True,
    }
    await db_session.commit()

    response = await HomeCollectionFlow().handle(
        session=session,
        message=FlowMessage(
            clinic_id=clinic_id,
            whatsapp_number=whatsapp_number,
            text="12 MG Road, Mumbai",
        ),
        db=db_session,
    )

    assert response == render_morning_slot_prompt()
    assert session.step == "select_slot"
    assert session.context["collection_address"] == "12 MG Road, Mumbai"


@pytest.mark.asyncio
async def test_home_collection_slot_creates_booking_audit_and_clears_session(
    db_session: AsyncSession,
    redis_client: Redis,
) -> None:
    clinic_id = uuid4()
    whatsapp_number = "+919999999996"
    patient, lipid, _urine, session = await create_home_collection_fixture(
        db_session,
        clinic_id,
        whatsapp_number,
    )
    session.step = "select_slot"
    session.context = {
        "selected_test_id": str(lipid.id),
        "selected_test_name": "Lipid Profile",
        "selected_test_price": "700.00",
        "requires_fasting": True,
        "collection_address": "12 MG Road, Mumbai",
    }
    await db_session.commit()

    response = await HomeCollectionFlow().handle(
        session=session,
        message=FlowMessage(clinic_id=clinic_id, whatsapp_number=whatsapp_number, text="1"),
        db=db_session,
    )

    booking = (
        await db_session.execute(
            select(TestBooking).where(
                TestBooking.clinic_id == clinic_id,
                TestBooking.patient_id == patient.id,
            ),
        )
    ).scalar_one()
    audit = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.clinic_id == clinic_id,
                AuditLog.action == "test_booking.created",
            ),
        )
    ).scalar_one()
    cached = await get_session_cached(whatsapp_number, str(clinic_id), db_session)

    assert response == HOME_COLLECTION_CONFIRMED.format(test_name="Lipid Profile")
    assert booking.test_id == lipid.id
    assert booking.booking_type == "home_collection"
    assert booking.collection_address == "12 MG Road, Mumbai"
    assert booking.collection_slot is not None
    assert booking.notes == "requires_fasting=true"
    assert audit.entity_id == booking.id
    assert session.is_active is False
    assert session.step == "home_collection_complete"
    assert cached is not None
    assert cached["is_active"] is False
