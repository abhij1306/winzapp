from decimal import Decimal
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.flows.base_flow import FlowMessage
from app.flows.test_booking_flow import TestBookingFlow
from app.models import AuditLog, Clinic, ConversationSession, Patient, Test, TestBooking
from app.services.cache import get_session_cached
from app.templates.hinglish import (
    TEST_BOOKING_CONFIRMED,
    render_category_prompt,
    render_test_confirmation_prompt,
    render_test_selection_prompt,
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


async def create_booking_fixture(
    db_session: AsyncSession,
    clinic_id: UUID,
    whatsapp_number: str,
) -> tuple[Patient, Test, Test, ConversationSession]:
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
    patient = Patient(
        id=uuid4(),
        clinic_id=clinic_id,
        whatsapp_number=whatsapp_number,
        opt_in=True,
    )
    cbc = Test(
        id=uuid4(),
        clinic_id=clinic_id,
        name="CBC",
        category="Blood",
        price=Decimal("300.00"),
        sort_order=1,
    )
    thyroid = Test(
        id=uuid4(),
        clinic_id=clinic_id,
        name="Thyroid Profile",
        category="Hormone",
        price=Decimal("500.00"),
        sort_order=2,
    )
    session = ConversationSession(
        clinic_id=clinic_id,
        patient_id=patient.id,
        whatsapp_number=whatsapp_number,
        flow="test_booking",
        step="select_category",
        context={},
    )
    db_session.add_all([patient, cbc, thyroid, session])
    await db_session.commit()
    return patient, cbc, thyroid, session


@pytest.mark.asyncio
async def test_test_booking_flow_starts_with_category_prompt(
    db_session: AsyncSession,
    redis_client: Redis,
) -> None:
    clinic_id = uuid4()
    whatsapp_number = "+919999999999"
    await create_booking_fixture(db_session, clinic_id, whatsapp_number)

    response = await TestBookingFlow().handle(
        session=None,
        message=FlowMessage(
            clinic_id=clinic_id,
            whatsapp_number=whatsapp_number,
            text="test book karna hai",
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

    assert response == render_category_prompt(["Blood", "Hormone"])
    assert session.step == "select_category"
    assert cached is not None
    assert cached["step"] == "select_category"


@pytest.mark.asyncio
async def test_category_selection_prompts_tests_in_category(
    db_session: AsyncSession,
    redis_client: Redis,
) -> None:
    clinic_id = uuid4()
    whatsapp_number = "+919999999998"
    _patient, cbc, _thyroid, session = await create_booking_fixture(
        db_session,
        clinic_id,
        whatsapp_number,
    )

    response = await TestBookingFlow().handle(
        session=session,
        message=FlowMessage(clinic_id=clinic_id, whatsapp_number=whatsapp_number, text="Blood"),
        db=db_session,
    )

    assert response == render_test_selection_prompt("Blood", ["CBC"])
    assert session.step == "select_test"
    assert session.context["category"] == "Blood"
    assert session.context["available_test_ids"] == [str(cbc.id)]


@pytest.mark.asyncio
async def test_test_selection_prompts_confirmation(
    db_session: AsyncSession,
    redis_client: Redis,
) -> None:
    clinic_id = uuid4()
    whatsapp_number = "+919999999997"
    _patient, cbc, _thyroid, session = await create_booking_fixture(
        db_session,
        clinic_id,
        whatsapp_number,
    )
    session.step = "select_test"
    session.context = {"category": "Blood", "available_test_ids": [str(cbc.id)]}
    await db_session.commit()

    response = await TestBookingFlow().handle(
        session=session,
        message=FlowMessage(clinic_id=clinic_id, whatsapp_number=whatsapp_number, text="CBC"),
        db=db_session,
    )

    assert response == render_test_confirmation_prompt("CBC", "300.00")
    assert session.step == "confirm_booking"
    assert session.context["selected_test_id"] == str(cbc.id)
    assert session.context["selected_test_name"] == "CBC"


@pytest.mark.asyncio
async def test_confirmation_creates_walkin_booking_audit_and_clears_session(
    db_session: AsyncSession,
    redis_client: Redis,
) -> None:
    clinic_id = uuid4()
    whatsapp_number = "+919999999996"
    patient, cbc, _thyroid, session = await create_booking_fixture(
        db_session,
        clinic_id,
        whatsapp_number,
    )
    session.step = "confirm_booking"
    session.context = {
        "selected_test_id": str(cbc.id),
        "selected_test_name": "CBC",
        "selected_test_price": "300.00",
    }
    await db_session.commit()

    response = await TestBookingFlow().handle(
        session=session,
        message=FlowMessage(clinic_id=clinic_id, whatsapp_number=whatsapp_number, text="haan"),
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

    assert response == TEST_BOOKING_CONFIRMED.format(test_name="CBC")
    assert booking.test_id == cbc.id
    assert booking.test_name == "CBC"
    assert booking.booking_type == "walkin"
    assert booking.status == "booked"
    assert booking.amount == Decimal("300.00")
    assert booking.payment_status == "pending"
    assert audit.entity_id == booking.id
    assert session.is_active is False
    assert session.step == "booking_complete"
    assert cached is not None
    assert cached["is_active"] is False
