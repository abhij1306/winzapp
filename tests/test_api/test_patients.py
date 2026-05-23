from __future__ import annotations

from collections.abc import AsyncGenerator
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


@pytest_asyncio.fixture
async def api_client(db_session: AsyncSession) -> AsyncGenerator[httpx.AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def create_patient_fixture(
    db_session: AsyncSession,
    owner_whatsapp: str = "+919000003001",
) -> tuple[Clinic, Patient, TestBooking]:
    suffix = owner_whatsapp[-4:]
    clinic = Clinic(
        id=uuid4(),
        name="Patient Diagnostics",
        owner_name="Owner",
        whatsapp_number=f"+91810000{suffix}",
        owner_whatsapp=owner_whatsapp,
        clinic_type="diagnostic",
        settings={"wa_phone_number_id": f"phone-patient-{suffix}"},
    )
    patient = Patient(
        clinic_id=clinic.id,
        whatsapp_number=f"+91770000{suffix}",
        name="Asha Sharma",
        age=34,
        gender="female",
        tags=["diabetes"],
        notes="Prefers morning",
    )
    test = Test(
        clinic_id=clinic.id,
        name="HbA1c",
        price=Decimal("450.00"),
        category="Diabetes",
    )
    booking = TestBooking(
        clinic_id=clinic.id,
        patient=patient,
        test=test,
        test_name="HbA1c",
        booking_type="walkin",
        status="processing",
        amount=Decimal("450.00"),
        payment_status="paid",
    )
    db_session.add_all([clinic, patient, test, booking])
    await db_session.commit()
    return clinic, patient, booking


def auth_headers(clinic: Clinic) -> dict[str, str]:
    token = create_access_token(clinic.owner_whatsapp, str(clinic.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_list_patients_searches_and_filters_by_clinic(
    db_session: AsyncSession,
    api_client: httpx.AsyncClient,
) -> None:
    clinic, patient, _booking = await create_patient_fixture(db_session)
    await create_patient_fixture(db_session, "+919000003002")

    response = await api_client.get(
        f"/api/v1/clinics/{clinic.id}/patients",
        headers=auth_headers(clinic),
        params={"q": "asha"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] == 1
    assert body["data"] == [
        {
            "id": str(patient.id),
            "whatsapp_number": patient.whatsapp_number,
            "name": "Asha Sharma",
            "age": 34,
            "gender": "female",
            "address": None,
            "opt_in": True,
            "tags": ["diabetes"],
            "last_visit_at": None,
            "notes": "Prefers morning",
        },
    ]


@pytest.mark.asyncio
async def test_get_patient_profile_includes_booking_history(
    db_session: AsyncSession,
    api_client: httpx.AsyncClient,
) -> None:
    clinic, patient, booking = await create_patient_fixture(db_session)

    response = await api_client.get(
        f"/api/v1/clinics/{clinic.id}/patients/{patient.id}",
        headers=auth_headers(clinic),
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["id"] == str(patient.id)
    assert body["bookings"] == [
        {
            "id": str(booking.id),
            "test_name": "HbA1c",
            "booking_type": "walkin",
            "status": "processing",
            "amount": "450.00",
            "payment_status": "paid",
            "booked_at": booking.booked_at.isoformat().replace("+00:00", "Z"),
        },
    ]


@pytest.mark.asyncio
async def test_update_patient_profile_writes_audit(
    db_session: AsyncSession,
    api_client: httpx.AsyncClient,
) -> None:
    clinic, patient, _booking = await create_patient_fixture(db_session)

    response = await api_client.put(
        f"/api/v1/clinics/{clinic.id}/patients/{patient.id}",
        headers=auth_headers(clinic),
        json={
            "name": "Asha S.",
            "age": 35,
            "address": "12 MG Road",
            "tags": ["diabetes", "morning"],
            "notes": "Call before visit",
        },
    )

    assert response.status_code == 200

    refreshed = (
        await db_session.execute(
            select(Patient).where(Patient.clinic_id == clinic.id, Patient.id == patient.id),
        )
    ).scalar_one()
    audit = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.clinic_id == clinic.id,
                AuditLog.action == "patient.updated",
                AuditLog.entity_id == patient.id,
            ),
        )
    ).scalar_one()

    assert response.json()["data"]["name"] == "Asha S."
    assert refreshed.age == 35
    assert refreshed.tags == ["diabetes", "morning"]
    assert audit.actor_type == "owner"
    assert audit.diff["before"]["name"] == "Asha Sharma"
    assert audit.diff["after"]["name"] == "Asha S."


@pytest.mark.asyncio
async def test_get_patient_profile_rejects_cross_clinic_access(
    db_session: AsyncSession,
    api_client: httpx.AsyncClient,
) -> None:
    clinic, _patient, _booking = await create_patient_fixture(db_session)
    _other_clinic, other_patient, _other_booking = await create_patient_fixture(
        db_session,
        "+919000003003",
    )

    response = await api_client.get(
        f"/api/v1/clinics/{clinic.id}/patients/{other_patient.id}",
        headers=auth_headers(clinic),
    )

    body = response.json()

    assert response.status_code == 404
    assert body["error"]["code"] == "PATIENT_NOT_FOUND"
    assert body["error"]["request_id"]
