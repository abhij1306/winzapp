from decimal import Decimal
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.flows.base_flow import FlowMessage
from app.flows.report_and_cancel_flows import CancellationFlow, ReportInquiryFlow
from app.models import AuditLog, Clinic, ConversationSession, Patient, Test, TestBooking
from app.services.cache import get_session_cached
from app.templates.hinglish import (
    CANCEL_BOOKING_CONFIRMED,
    CANCEL_BOOKING_NOT_FOUND,
    REPORT_STATUS_NOT_FOUND,
    render_report_status_pending,
    render_report_status_ready,
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


async def create_report_fixture(
    db_session: AsyncSession,
    clinic_id: UUID,
    whatsapp_number: str,
    *,
    booking_status: str | None = "processing",
    report_file_path: str | None = None,
) -> tuple[Patient, Test, ConversationSession, TestBooking | None]:
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
    test = Test(
        id=uuid4(),
        clinic_id=clinic_id,
        name="CBC",
        category="Blood",
        price=Decimal("300.00"),
        sort_order=1,
    )
    session = ConversationSession(
        clinic_id=clinic_id,
        patient_id=patient.id,
        whatsapp_number=whatsapp_number,
        flow="report_inquiry",
        step="lookup_report",
        context={},
    )
    booking = None
    if booking_status is not None:
        booking = TestBooking(
            clinic_id=clinic_id,
            patient_id=patient.id,
            test_id=test.id,
            test_name="CBC",
            booking_type="walkin",
            status=booking_status,
            amount=Decimal("300.00"),
            payment_status="paid",
            payment_method="manual_offline",
            report_file_path=report_file_path,
        )
        db_session.add(booking)
    db_session.add_all([patient, test, session])
    await db_session.commit()
    return patient, test, session, booking


@pytest.mark.asyncio
async def test_report_inquiry_returns_pending_status_and_clears_session(
    db_session: AsyncSession,
    redis_client: Redis,
) -> None:
    clinic_id = uuid4()
    whatsapp_number = "+919999999999"
    _patient, _test, session, _booking = await create_report_fixture(
        db_session,
        clinic_id,
        whatsapp_number,
        booking_status="processing",
    )

    response = await ReportInquiryFlow().handle(
        session=session,
        message=FlowMessage(
            clinic_id=clinic_id,
            whatsapp_number=whatsapp_number,
            text="report status",
        ),
        db=db_session,
    )

    cached = await get_session_cached(whatsapp_number, str(clinic_id), db_session)

    assert response == render_report_status_pending("CBC", "processing")
    assert session.is_active is False
    assert session.step == "report_inquiry_complete"
    assert cached is not None
    assert cached["is_active"] is False


@pytest.mark.asyncio
async def test_report_inquiry_returns_ready_when_report_file_exists(
    db_session: AsyncSession,
    redis_client: Redis,
) -> None:
    clinic_id = uuid4()
    whatsapp_number = "+919999999998"
    _patient, _test, session, _booking = await create_report_fixture(
        db_session,
        clinic_id,
        whatsapp_number,
        booking_status="report_ready",
        report_file_path="reports/cbc.pdf",
    )

    response = await ReportInquiryFlow().handle(
        session=session,
        message=FlowMessage(clinic_id=clinic_id, whatsapp_number=whatsapp_number, text="report"),
        db=db_session,
    )

    assert response == render_report_status_ready("CBC")
    assert session.is_active is False
    assert session.step == "report_inquiry_complete"


@pytest.mark.asyncio
async def test_report_inquiry_without_booking_returns_not_found(
    db_session: AsyncSession,
    redis_client: Redis,
) -> None:
    clinic_id = uuid4()
    whatsapp_number = "+919999999997"
    _patient, _test, session, _booking = await create_report_fixture(
        db_session,
        clinic_id,
        whatsapp_number,
        booking_status=None,
    )

    response = await ReportInquiryFlow().handle(
        session=session,
        message=FlowMessage(clinic_id=clinic_id, whatsapp_number=whatsapp_number, text="report"),
        db=db_session,
    )

    assert response == REPORT_STATUS_NOT_FOUND
    assert session.is_active is False
    assert session.step == "report_inquiry_complete"


@pytest.mark.asyncio
async def test_cancellation_soft_cancels_latest_booking_and_writes_audit(
    db_session: AsyncSession,
    redis_client: Redis,
) -> None:
    clinic_id = uuid4()
    whatsapp_number = "+919999999996"
    patient, _test, session, booking = await create_report_fixture(
        db_session,
        clinic_id,
        whatsapp_number,
        booking_status="booked",
    )
    assert booking is not None
    session.flow = "cancel"
    session.step = "cancel_booking"
    await db_session.commit()

    response = await CancellationFlow().handle(
        session=session,
        message=FlowMessage(
            clinic_id=clinic_id,
            whatsapp_number=whatsapp_number,
            text="cancel booking",
        ),
        db=db_session,
    )

    refreshed_booking = (
        await db_session.execute(
            select(TestBooking).where(
                TestBooking.clinic_id == clinic_id,
                TestBooking.id == booking.id,
            ),
        )
    ).scalar_one()
    audit = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.clinic_id == clinic_id,
                AuditLog.action == "test_booking.cancelled",
            ),
        )
    ).scalar_one()
    cached = await get_session_cached(whatsapp_number, str(clinic_id), db_session)

    assert response == CANCEL_BOOKING_CONFIRMED.format(test_name="CBC")
    assert refreshed_booking.status == "cancelled"
    assert refreshed_booking.deleted_at is not None
    assert refreshed_booking.deleted_by == patient.id
    assert audit.entity_id == booking.id
    assert audit.actor_id == patient.id
    assert audit.diff == {"before": {"status": "booked"}, "after": {"status": "cancelled"}}
    assert session.is_active is False
    assert session.step == "cancellation_complete"
    assert cached is not None
    assert cached["is_active"] is False


@pytest.mark.asyncio
async def test_cancellation_without_booking_returns_not_found(
    db_session: AsyncSession,
    redis_client: Redis,
) -> None:
    clinic_id = uuid4()
    whatsapp_number = "+919999999995"
    _patient, _test, session, _booking = await create_report_fixture(
        db_session,
        clinic_id,
        whatsapp_number,
        booking_status=None,
    )

    response = await CancellationFlow().handle(
        session=session,
        message=FlowMessage(
            clinic_id=clinic_id,
            whatsapp_number=whatsapp_number,
            text="cancel booking",
        ),
        db=db_session,
    )

    audit_count = len(
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.clinic_id == clinic_id,
                    AuditLog.action == "test_booking.cancelled",
                ),
            )
        ).scalars().all(),
    )

    assert response == CANCEL_BOOKING_NOT_FOUND
    assert audit_count == 0
    assert session.is_active is False
    assert session.step == "cancellation_complete"
