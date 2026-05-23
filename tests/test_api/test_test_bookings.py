from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.main import app
from app.models import AuditLog, Clinic, Patient, Test, TestBooking
from app.services.auth import create_access_token
from app.utils.datetime_utils import now_ist


@pytest_asyncio.fixture
async def api_client(db_session: AsyncSession) -> AsyncGenerator[httpx.AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def create_booking_fixture(
    db_session: AsyncSession,
    owner_whatsapp: str = "+919000001001",
) -> tuple[Clinic, Patient, Test, TestBooking]:
    suffix = owner_whatsapp[-4:]
    clinic = Clinic(
        id=uuid4(),
        name="Ops Diagnostics",
        owner_name="Owner",
        whatsapp_number=f"+91810000{suffix}",
        owner_whatsapp=owner_whatsapp,
        clinic_type="diagnostic",
        address="MG Road",
        city="Bhopal",
        pincode="462001",
        timezone="Asia/Kolkata",
        plan="diagnostic",
        settings={"wa_phone_number_id": f"phone-{suffix}"},
    )
    patient = Patient(
        clinic_id=clinic.id,
        whatsapp_number=f"+91770000{suffix}",
        name="Asha Sharma",
    )
    test = Test(
        clinic_id=clinic.id,
        name="CBC",
        price=Decimal("300.00"),
        category="Blood",
    )
    booking = TestBooking(
        clinic_id=clinic.id,
        patient=patient,
        test=test,
        test_name="CBC",
        booking_type="walkin",
        status="booked",
        amount=Decimal("300.00"),
        payment_status="pending",
        booked_at=now_ist(),
    )
    db_session.add_all([clinic, patient, test, booking])
    await db_session.commit()
    return clinic, patient, test, booking


def auth_headers(clinic: Clinic) -> dict[str, str]:
    token = create_access_token(clinic.owner_whatsapp, str(clinic.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_list_test_bookings_filters_by_status_and_clinic(
    db_session: AsyncSession,
    api_client: httpx.AsyncClient,
) -> None:
    clinic, _patient, _test, booking = await create_booking_fixture(db_session)
    other_clinic, other_patient, other_test, _other_booking = await create_booking_fixture(
        db_session,
        "+919000001002",
    )
    db_session.add(
        TestBooking(
            clinic_id=other_clinic.id,
            patient=other_patient,
            test=other_test,
            test_name="CBC",
            booking_type="walkin",
            status="booked",
            payment_status="pending",
        ),
    )
    await db_session.commit()

    response = await api_client.get(
        f"/api/v1/clinics/{clinic.id}/test-bookings",
        headers=auth_headers(clinic),
        params={"status": "booked"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] == 1
    assert body["data"] == [
        {
            "id": str(booking.id),
            "patient_id": str(booking.patient_id),
            "patient_name": "Asha Sharma",
            "patient_whatsapp": booking.patient.whatsapp_number,
            "test_id": str(booking.test_id),
            "test_name": "CBC",
            "booking_type": "walkin",
            "status": "booked",
            "collection_address": None,
            "collection_slot": None,
            "technician_name": None,
            "amount": "300.00",
            "payment_status": "pending",
            "payment_method": None,
            "report_file_path": None,
            "report_delivered_at": None,
            "booked_at": booking.booked_at.isoformat(),
            "notes": None,
        },
    ]


@pytest.mark.asyncio
async def test_create_test_booking_uses_clinic_patient_and_test_and_writes_audit(
    db_session: AsyncSession,
    api_client: httpx.AsyncClient,
) -> None:
    clinic, patient, test, _booking = await create_booking_fixture(db_session)

    response = await api_client.post(
        f"/api/v1/clinics/{clinic.id}/test-bookings",
        headers=auth_headers(clinic),
        json={
            "patient_id": str(patient.id),
            "test_id": str(test.id),
            "booking_type": "home_collection",
            "collection_address": "12 MG Road",
            "payment_status": "partial",
            "payment_method": "cash",
            "notes": "Fasting advised by clinic",
        },
    )

    body = response.json()
    created = (
        await db_session.execute(
            select(TestBooking).where(
                TestBooking.clinic_id == clinic.id,
                TestBooking.id == body["data"]["id"],
            ),
        )
    ).scalar_one()
    audit = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.clinic_id == clinic.id,
                AuditLog.action == "test_booking.created",
                AuditLog.entity_id == created.id,
            ),
        )
    ).scalar_one()

    assert response.status_code == 201
    assert body["data"]["test_name"] == "CBC"
    assert body["data"]["amount"] == "300.00"
    assert created.patient_id == patient.id
    assert created.test_id == test.id
    assert created.booking_type == "home_collection"
    assert created.collection_address == "12 MG Road"
    assert audit.actor_type == "owner"


@pytest.mark.asyncio
async def test_update_test_booking_changes_operational_fields_and_audits(
    db_session: AsyncSession,
    api_client: httpx.AsyncClient,
) -> None:
    clinic, _patient, _test, booking = await create_booking_fixture(db_session)
    collection_slot = datetime.fromisoformat("2026-06-01T09:30:00+05:30")

    response = await api_client.put(
        f"/api/v1/clinics/{clinic.id}/test-bookings/{booking.id}",
        headers=auth_headers(clinic),
        json={
            "status": "sample_collected",
            "payment_status": "paid",
            "payment_method": "upi",
            "technician_name": "Ravi",
            "collection_slot": collection_slot.isoformat(),
        },
    )

    refreshed = (
        await db_session.execute(
            select(TestBooking).where(
                TestBooking.clinic_id == clinic.id,
                TestBooking.id == booking.id,
            ),
        )
    ).scalar_one()
    audit = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.clinic_id == clinic.id,
                AuditLog.action == "test_booking.updated",
                AuditLog.entity_id == booking.id,
            ),
        )
    ).scalar_one()

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "sample_collected"
    assert refreshed.payment_status == "paid"
    assert refreshed.payment_method == "upi"
    assert refreshed.technician_name == "Ravi"
    assert audit.diff["before"]["status"] == "booked"
    assert audit.diff["after"]["status"] == "sample_collected"


@pytest.mark.asyncio
async def test_delete_test_booking_soft_deletes_and_writes_audit(
    db_session: AsyncSession,
    api_client: httpx.AsyncClient,
) -> None:
    clinic, _patient, _test, booking = await create_booking_fixture(db_session)

    response = await api_client.delete(
        f"/api/v1/clinics/{clinic.id}/test-bookings/{booking.id}",
        headers=auth_headers(clinic),
    )

    refreshed = (
        await db_session.execute(
            select(TestBooking).where(
                TestBooking.clinic_id == clinic.id,
                TestBooking.id == booking.id,
            ),
        )
    ).scalar_one()
    audit = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.clinic_id == clinic.id,
                AuditLog.action == "test_booking.deleted",
                AuditLog.entity_id == booking.id,
            ),
        )
    ).scalar_one()

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "cancelled"
    assert refreshed.deleted_at is not None
    assert refreshed.deleted_by is None
    assert audit.actor_type == "owner"


@pytest.mark.asyncio
async def test_create_test_booking_rejects_patient_from_another_clinic(
    db_session: AsyncSession,
    api_client: httpx.AsyncClient,
) -> None:
    clinic, _patient, test, _booking = await create_booking_fixture(db_session)
    _other_clinic, other_patient, _other_test, _other_booking = await create_booking_fixture(
        db_session,
        "+919000001003",
    )

    response = await api_client.post(
        f"/api/v1/clinics/{clinic.id}/test-bookings",
        headers=auth_headers(clinic),
        json={
            "patient_id": str(other_patient.id),
            "test_id": str(test.id),
            "booking_type": "walkin",
        },
    )

    body = response.json()

    assert response.status_code == 404
    assert body["error"]["code"] == "PATIENT_NOT_FOUND"
    assert body["error"]["request_id"]

