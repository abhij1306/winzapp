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
from app.models import Clinic, Patient, RecallSchedule, Test, TestBooking
from app.services.recall_scheduling import maybe_create_recall_for_booking
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


async def create_recall_fixture(
    db_session: AsyncSession,
    clinic_id: UUID,
    test_name: str,
    *,
    recall_enabled: bool = True,
) -> tuple[Patient, TestBooking]:
    db_session.add(
        Clinic(
            id=clinic_id,
            name="Demo Diagnostics",
            whatsapp_number="+919000000001",
            owner_whatsapp="+919000000002",
            clinic_type="diagnostic",
            settings={"features": {"recall_automation": recall_enabled}},
        ),
    )
    patient = Patient(
        id=uuid4(),
        clinic_id=clinic_id,
        whatsapp_number="+919876543210",
        opt_in=True,
    )
    test = Test(
        id=uuid4(),
        clinic_id=clinic_id,
        name=test_name,
        category="Diagnostics",
        price=Decimal("450.00"),
        sort_order=1,
    )
    booking = TestBooking(
        clinic_id=clinic_id,
        patient_id=patient.id,
        test_id=test.id,
        test_name=test_name,
        booking_type="walkin",
        status="delivered",
        amount=Decimal("450.00"),
        payment_status="paid",
        payment_method="manual_offline",
        report_delivered_at=now_ist(),
    )
    db_session.add_all([patient, test, booking])
    await db_session.commit()
    return patient, booking


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("test_name", "trigger_type", "days"),
    [
        ("HbA1c", "hba1c_quarterly", 90),
        ("Diabetes Package (HbA1c + FBS + PPBS)", "hba1c_quarterly", 90),
        ("Thyroid Profile", "thyroid_6month", 180),
        ("Full Body Checkup", "annual_checkup", 365),
        ("Annual Health Checkup", "annual_checkup", 365),
    ],
)
async def test_recall_scheduling_creates_known_diagnostics_rules(
    db_session: AsyncSession,
    redis_client: Redis,
    test_name: str,
    trigger_type: str,
    days: int,
) -> None:
    clinic_id = uuid4()
    patient, booking = await create_recall_fixture(db_session, clinic_id, test_name)

    recall = await maybe_create_recall_for_booking(db_session, booking)

    assert recall is not None
    assert recall.clinic_id == clinic_id
    assert recall.patient_id == patient.id
    assert recall.trigger_type == trigger_type
    assert recall.status == "pending"
    assert recall.message_template == "recall_reminder"
    assert recall.reference_id == booking.id
    assert recall.trigger_at.date() == (now_ist() + timedelta(days=days)).date()


@pytest.mark.asyncio
async def test_recall_scheduling_skips_unknown_tests(
    db_session: AsyncSession,
    redis_client: Redis,
) -> None:
    clinic_id = uuid4()
    _patient, booking = await create_recall_fixture(db_session, clinic_id, "CBC")

    recall = await maybe_create_recall_for_booking(db_session, booking)

    recall_count = len((await db_session.execute(select(RecallSchedule))).scalars().all())

    assert recall is None
    assert recall_count == 0


@pytest.mark.asyncio
async def test_recall_scheduling_skips_when_feature_disabled(
    db_session: AsyncSession,
    redis_client: Redis,
) -> None:
    clinic_id = uuid4()
    _patient, booking = await create_recall_fixture(
        db_session,
        clinic_id,
        "HbA1c",
        recall_enabled=False,
    )

    recall = await maybe_create_recall_for_booking(db_session, booking)

    assert recall is None


@pytest.mark.asyncio
async def test_recall_scheduling_is_idempotent_per_booking(
    db_session: AsyncSession,
    redis_client: Redis,
) -> None:
    clinic_id = uuid4()
    _patient, booking = await create_recall_fixture(db_session, clinic_id, "HbA1c")

    first = await maybe_create_recall_for_booking(db_session, booking)
    second = await maybe_create_recall_for_booking(db_session, booking)
    recalls = (await db_session.execute(select(RecallSchedule))).scalars().all()

    assert first is not None
    assert second is not None
    assert first.id == second.id
    assert len(recalls) == 1
