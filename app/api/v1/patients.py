from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.api.errors import error_response
from app.api.v1.test_bookings import authorize_request
from app.database import get_db
from app.models import Patient, TestBooking
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.patient import (
    PatientBookingData,
    PatientData,
    PatientProfileData,
    PatientProfileResponse,
    PatientResponse,
    PatientUpdateRequest,
)
from app.services.audit import write_audit

router = APIRouter(prefix="/clinics/{clinic_id}/patients", tags=["patients"])


@router.get("", response_model=PaginatedResponse[PatientData])
async def list_patients(
    clinic_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    q: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedResponse[PatientData]:
    owner = await authorize_request(db, authorization, clinic_id)
    if isinstance(owner, JSONResponse):
        return cast(PaginatedResponse[PatientData], owner)

    filters = patient_filters(clinic_id, q)
    total = await count_patients(db, filters)
    statement = (
        select(Patient)
        .where(*filters)
        .order_by(Patient.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    patients = (await db.execute(statement)).scalars().all()
    return PaginatedResponse[PatientData](
        data=[patient_data(patient) for patient in patients],
        pagination=PaginationMeta(page=page, page_size=page_size, total=total),
    )


@router.get("/{patient_id}", response_model=PatientProfileResponse)
async def get_patient(
    clinic_id: str,
    patient_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> PatientProfileResponse:
    owner = await authorize_request(db, authorization, clinic_id)
    if isinstance(owner, JSONResponse):
        return cast(PatientProfileResponse, owner)

    patient = await find_patient(db, clinic_id, patient_id)
    if patient is None:
        return patient_not_found()
    bookings = await find_patient_bookings(db, clinic_id, patient_id)
    return PatientProfileResponse(data=patient_profile_data(patient, bookings))


@router.put("/{patient_id}", response_model=PatientResponse)
async def update_patient(
    clinic_id: str,
    patient_id: str,
    payload: PatientUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> PatientResponse:
    owner = await authorize_request(db, authorization, clinic_id)
    if isinstance(owner, JSONResponse):
        return cast(PatientResponse, owner)

    patient = await find_patient(db, clinic_id, patient_id)
    if patient is None:
        return cast(PatientResponse, patient_not_found())

    before = patient_snapshot(patient)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(patient, field, value)
    await db.commit()
    await write_patient_audit(db, patient, before)
    return PatientResponse(data=patient_data(patient))


def patient_filters(clinic_id: str, q: str | None) -> list[ColumnElement[bool]]:
    filters: list[ColumnElement[bool]] = [
        Patient.clinic_id == clinic_id,
        Patient.deleted_at.is_(None),
    ]
    if q:
        search = f"%{q}%"
        filters.append(or_(Patient.name.ilike(search), Patient.whatsapp_number.ilike(search)))
    return filters


async def count_patients(db: AsyncSession, filters: list[ColumnElement[bool]]) -> int:
    statement = select(func.count()).select_from(Patient).where(*filters)
    return int((await db.execute(statement)).scalar_one())


async def find_patient(db: AsyncSession, clinic_id: str, patient_id: str) -> Patient | None:
    statement = select(Patient).where(
        Patient.clinic_id == clinic_id,
        Patient.id == patient_id,
        Patient.deleted_at.is_(None),
    )
    return (await db.execute(statement)).scalar_one_or_none()


async def find_patient_bookings(
    db: AsyncSession,
    clinic_id: str,
    patient_id: str,
) -> list[TestBooking]:
    statement = (
        select(TestBooking)
        .where(
            TestBooking.clinic_id == clinic_id,
            TestBooking.patient_id == patient_id,
            TestBooking.deleted_at.is_(None),
        )
        .order_by(TestBooking.booked_at.desc(), TestBooking.created_at.desc())
    )
    return list((await db.execute(statement)).scalars().all())


def patient_not_found() -> PatientProfileResponse:
    return cast(
        PatientProfileResponse,
        error_response(404, "PATIENT_NOT_FOUND", "Patient was not found."),
    )


async def write_patient_audit(
    db: AsyncSession,
    patient: Patient,
    before: dict[str, object],
) -> None:
    await write_audit(
        db=db,
        clinic_id=patient.clinic_id,
        actor_type="owner",
        action="patient.updated",
        entity_type="patient",
        entity_id=patient.id if isinstance(patient.id, UUID) else None,
        diff={"before": before, "after": patient_snapshot(patient)},
    )


def patient_data(patient: Patient) -> PatientData:
    return PatientData(**patient_snapshot(patient))


def patient_profile_data(patient: Patient, bookings: list[TestBooking]) -> PatientProfileData:
    return PatientProfileData(
        **patient_snapshot(patient),
        bookings=[booking_history_data(booking) for booking in bookings],
    )


def booking_history_data(booking: TestBooking) -> PatientBookingData:
    return PatientBookingData(
        id=str(booking.id),
        test_name=booking.test_name,
        booking_type=booking.booking_type,
        status=booking.status,
        amount=booking.amount,
        payment_status=booking.payment_status,
        booked_at=booking.booked_at,
    )


def patient_snapshot(patient: Patient) -> dict[str, object]:
    return {
        "id": str(patient.id),
        "whatsapp_number": patient.whatsapp_number,
        "name": patient.name,
        "age": patient.age,
        "gender": patient.gender,
        "address": patient.address,
        "opt_in": patient.opt_in,
        "tags": patient.tags,
        "last_visit_at": patient.last_visit_at,
        "notes": patient.notes,
    }
