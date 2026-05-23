from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.flows.admin_flow import AdminFlow
from app.flows.base_flow import FlowMessage
from app.models import AuditLog, Clinic, Patient, Test, TestBooking
from app.templates.hinglish import (
    ADMIN_PATIENT_OPTED_OUT,
    ADMIN_REPORT_NOT_FOUND,
    ADMIN_REPORT_SENT,
    ADMIN_UNAUTHORIZED,
    render_admin_daily_stats,
    render_admin_pending_reports,
    render_admin_today_bookings,
)
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


async def create_admin_fixture(
    db_session: AsyncSession,
    clinic_id: UUID,
    owner_whatsapp: str,
) -> tuple[Patient, Test, TestBooking, TestBooking, TestBooking]:
    db_session.add(
        Clinic(
            id=clinic_id,
            name="Demo Diagnostics",
            whatsapp_number="+919000000001",
            owner_whatsapp=owner_whatsapp,
            clinic_type="diagnostic",
            settings={"wa_phone_number_id": "phone-number-id"},
        ),
    )
    patient = Patient(
        id=uuid4(),
        clinic_id=clinic_id,
        whatsapp_number="+919888887777",
        name="Anita",
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
    today = now_ist()
    ready_report = TestBooking(
        clinic_id=clinic_id,
        patient_id=patient.id,
        test_id=cbc.id,
        test_name="CBC",
        booking_type="walkin",
        status="report_ready",
        amount=Decimal("300.00"),
        payment_status="paid",
        payment_method="manual_offline",
        report_file_path="https://reports.example/cbc.pdf",
        booked_at=today,
    )
    home_pending = TestBooking(
        clinic_id=clinic_id,
        patient_id=patient.id,
        test_id=cbc.id,
        test_name="Thyroid Profile",
        booking_type="home_collection",
        status="processing",
        amount=Decimal("500.00"),
        payment_status="paid",
        payment_method="manual_offline",
        booked_at=today,
    )
    old_booking = TestBooking(
        clinic_id=clinic_id,
        patient_id=patient.id,
        test_id=cbc.id,
        test_name="Old Lipid",
        booking_type="walkin",
        status="booked",
        amount=Decimal("700.00"),
        payment_status="pending",
        payment_method="manual_offline",
        booked_at=today - timedelta(days=2),
    )
    db_session.add_all([patient, cbc, ready_report, home_pending, old_booking])
    await db_session.commit()
    return patient, cbc, ready_report, home_pending, old_booking


@pytest.mark.asyncio
async def test_admin_flow_rejects_non_owner_sender(
    db_session: AsyncSession,
    redis_client: Redis,
) -> None:
    clinic_id = uuid4()
    await create_admin_fixture(db_session, clinic_id, "+919000000002")

    response = await AdminFlow().handle(
        session=None,
        message=FlowMessage(
            clinic_id=clinic_id,
            whatsapp_number="+919000000003",
            text="aaj ke tests",
        ),
        db=db_session,
    )

    assert response == ADMIN_UNAUTHORIZED


@pytest.mark.asyncio
async def test_admin_today_tests_command_lists_only_today_bookings(
    db_session: AsyncSession,
    redis_client: Redis,
) -> None:
    clinic_id = uuid4()
    owner_whatsapp = "+919000000002"
    _patient, _cbc, ready_report, home_pending, _old_booking = await create_admin_fixture(
        db_session,
        clinic_id,
        owner_whatsapp,
    )

    response = await AdminFlow().handle(
        session=None,
        message=FlowMessage(
            clinic_id=clinic_id,
            whatsapp_number=owner_whatsapp,
            text="aaj ke tests",
        ),
        db=db_session,
    )

    assert response == render_admin_today_bookings([ready_report, home_pending])


@pytest.mark.asyncio
async def test_admin_pending_reports_command_lists_undelivered_reports(
    db_session: AsyncSession,
    redis_client: Redis,
) -> None:
    clinic_id = uuid4()
    owner_whatsapp = "+919000000002"
    _patient, _cbc, ready_report, home_pending, _old_booking = await create_admin_fixture(
        db_session,
        clinic_id,
        owner_whatsapp,
    )

    response = await AdminFlow().handle(
        session=None,
        message=FlowMessage(
            clinic_id=clinic_id,
            whatsapp_number=owner_whatsapp,
            text="pending reports dikhao",
        ),
        db=db_session,
    )

    assert response == render_admin_pending_reports([ready_report, home_pending])


@pytest.mark.asyncio
async def test_admin_send_report_delivers_document_and_audits(
    db_session: AsyncSession,
    redis_client: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clinic_id = uuid4()
    owner_whatsapp = "+919000000002"
    patient, _cbc, ready_report, _home_pending, _old_booking = await create_admin_fixture(
        db_session,
        clinic_id,
        owner_whatsapp,
    )
    sent_payloads = []

    async def fake_send_document(
        phone_number_id: str,
        to: str,
        access_token: str,
        document_url: str,
        filename: str,
        caption: str | None = None,
    ) -> dict[str, object]:
        sent_payloads.append(
            {
                "phone_number_id": phone_number_id,
                "to": to,
                "access_token": access_token,
                "document_url": document_url,
                "filename": filename,
                "caption": caption,
            },
        )
        return {"messages": [{"id": "wamid.report"}]}

    monkeypatch.setattr("app.services.whatsapp_sender.send_document", fake_send_document)

    response = await AdminFlow().handle(
        session=None,
        message=FlowMessage(
            clinic_id=clinic_id,
            whatsapp_number=owner_whatsapp,
            text=f"send report {ready_report.id}",
        ),
        db=db_session,
    )

    refreshed_booking = (
        await db_session.execute(
            select(TestBooking).where(
                TestBooking.clinic_id == clinic_id,
                TestBooking.id == ready_report.id,
            ),
        )
    ).scalar_one()
    audit = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.clinic_id == clinic_id,
                AuditLog.action == "report.delivered",
            ),
        )
    ).scalar_one()

    assert response == ADMIN_REPORT_SENT.format(test_name="CBC")
    assert sent_payloads == [
        {
            "phone_number_id": "phone-number-id",
            "to": patient.whatsapp_number,
            "access_token": get_settings().wa_access_token,
            "document_url": "https://reports.example/cbc.pdf",
            "filename": "CBC_report.pdf",
            "caption": "CBC report attached hai.",
        },
    ]
    assert refreshed_booking.status == "delivered"
    assert refreshed_booking.report_delivered_at is not None
    assert refreshed_booking.report_status_notified is True
    assert audit.entity_id == ready_report.id


@pytest.mark.asyncio
async def test_admin_send_report_without_ready_file_returns_not_found(
    db_session: AsyncSession,
    redis_client: Redis,
) -> None:
    clinic_id = uuid4()
    owner_whatsapp = "+919000000002"
    _patient, _cbc, _ready_report, home_pending, _old_booking = await create_admin_fixture(
        db_session,
        clinic_id,
        owner_whatsapp,
    )

    response = await AdminFlow().handle(
        session=None,
        message=FlowMessage(
            clinic_id=clinic_id,
            whatsapp_number=owner_whatsapp,
            text=f"send report {home_pending.id}",
        ),
        db=db_session,
    )

    assert response == ADMIN_REPORT_NOT_FOUND


@pytest.mark.asyncio
async def test_admin_send_report_rejects_opted_out_patient(
    db_session: AsyncSession,
    redis_client: Redis,
) -> None:
    clinic_id = uuid4()
    owner_whatsapp = "+919000000002"
    patient, _cbc, ready_report, _home_pending, _old_booking = await create_admin_fixture(
        db_session,
        clinic_id,
        owner_whatsapp,
    )
    patient.opt_in = False
    await db_session.commit()

    response = await AdminFlow().handle(
        session=None,
        message=FlowMessage(
            clinic_id=clinic_id,
            whatsapp_number=owner_whatsapp,
            text=f"send report {ready_report.id}",
        ),
        db=db_session,
    )

    assert response == ADMIN_PATIENT_OPTED_OUT


@pytest.mark.asyncio
async def test_admin_cancel_booking_command_soft_cancels_and_audits(
    db_session: AsyncSession,
    redis_client: Redis,
) -> None:
    clinic_id = uuid4()
    owner_whatsapp = "+919000000002"
    _patient, _cbc, _ready_report, home_pending, _old_booking = await create_admin_fixture(
        db_session,
        clinic_id,
        owner_whatsapp,
    )

    response = await AdminFlow().handle(
        session=None,
        message=FlowMessage(
            clinic_id=clinic_id,
            whatsapp_number=owner_whatsapp,
            text=f"cancel booking {home_pending.id}",
        ),
        db=db_session,
    )

    refreshed_booking = (
        await db_session.execute(
            select(TestBooking).where(
                TestBooking.clinic_id == clinic_id,
                TestBooking.id == home_pending.id,
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

    assert response == "Thyroid Profile booking cancel kar di gayi hai."
    assert refreshed_booking.status == "cancelled"
    assert refreshed_booking.deleted_at is not None
    assert refreshed_booking.deleted_by is None
    assert audit.entity_id == home_pending.id
    assert audit.actor_type == "owner"


@pytest.mark.asyncio
async def test_admin_daily_stats_command_returns_today_counts(
    db_session: AsyncSession,
    redis_client: Redis,
) -> None:
    clinic_id = uuid4()
    owner_whatsapp = "+919000000002"
    await create_admin_fixture(db_session, clinic_id, owner_whatsapp)

    response = await AdminFlow().handle(
        session=None,
        message=FlowMessage(
            clinic_id=clinic_id,
            whatsapp_number=owner_whatsapp,
            text="daily stats",
        ),
        db=db_session,
    )

    assert response == render_admin_daily_stats(
        {
            "bookings_today": 2,
            "home_collection_today": 1,
            "walkin_today": 1,
            "pending_reports": 2,
            "reports_delivered_today": 0,
        },
    )
