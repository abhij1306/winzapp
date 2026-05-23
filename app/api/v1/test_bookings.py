from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.api.auth_context import CurrentOwner, authenticate_owner
from app.api.errors import error_response
from app.database import get_db, set_tenant_context
from app.models import Clinic, Patient, Test, TestBooking
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.test_booking import (
    BookingStatus,
    BookingType,
    PaymentStatus,
    TestBookingCreateRequest,
    TestBookingData,
    TestBookingResponse,
    TestBookingUpdateRequest,
)
from app.services.audit import write_audit
from app.utils.datetime_utils import now_ist

router = APIRouter(prefix="/clinics/{clinic_id}/test-bookings", tags=["test-bookings"])


@router.get("", response_model=PaginatedResponse[TestBookingData])
async def list_test_bookings(
    clinic_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    status: Annotated[BookingStatus | None, Query()] = None,
    booking_type: Annotated[BookingType | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedResponse[TestBookingData]:
    owner = await authorize_request(db, authorization, clinic_id)
    if isinstance(owner, JSONResponse):
        return cast(PaginatedResponse[TestBookingData], owner)

    filters = booking_filters(clinic_id, status, booking_type)
    total = await count_bookings(db, filters)
    statement = (
        select(TestBooking)
        .where(*filters)
        .order_by(TestBooking.booked_at.desc(), TestBooking.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    bookings = (await db.execute(statement)).scalars().all()
    return PaginatedResponse[TestBookingData](
        data=[booking_data(booking) for booking in bookings],
        pagination=PaginationMeta(page=page, page_size=page_size, total=total),
    )


@router.post("", response_model=TestBookingResponse, status_code=201)
async def create_test_booking(
    clinic_id: str,
    payload: TestBookingCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> TestBookingResponse:
    owner = await authorize_request(db, authorization, clinic_id)
    if isinstance(owner, JSONResponse):
        return cast(TestBookingResponse, owner)

    patient = await find_patient(db, clinic_id, payload.patient_id)
    if patient is None:
        return cast(
            TestBookingResponse,
            error_response(404, "PATIENT_NOT_FOUND", "Patient was not found."),
        )
    test = await find_test(db, clinic_id, payload.test_id) if payload.test_id else None
    if payload.test_id and test is None:
        return cast(
            TestBookingResponse,
            error_response(404, "TEST_NOT_FOUND", "Test was not found."),
        )

    booking = build_booking(clinic_id, payload, patient, test)
    db.add(booking)
    await db.commit()
    await db.refresh(booking, ["patient", "test"])
    await write_booking_audit(db, booking, "test_booking.created", None)
    return TestBookingResponse(data=booking_data(booking))


@router.put("/{booking_id}", response_model=TestBookingResponse)
async def update_test_booking(
    clinic_id: str,
    booking_id: str,
    payload: TestBookingUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> TestBookingResponse:
    owner = await authorize_request(db, authorization, clinic_id)
    if isinstance(owner, JSONResponse):
        return cast(TestBookingResponse, owner)

    booking = await find_booking(db, clinic_id, booking_id)
    if booking is None:
        return cast(
            TestBookingResponse,
            error_response(404, "BOOKING_NOT_FOUND", "Booking was not found."),
        )

    before = booking_snapshot(booking)
    apply_booking_update(booking, payload)
    await db.commit()
    await db.refresh(booking, ["patient", "test"])
    await write_booking_audit(db, booking, "test_booking.updated", before)
    return TestBookingResponse(data=booking_data(booking))


@router.delete("/{booking_id}", response_model=TestBookingResponse)
async def delete_test_booking(
    clinic_id: str,
    booking_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> TestBookingResponse:
    owner = await authorize_request(db, authorization, clinic_id)
    if isinstance(owner, JSONResponse):
        return cast(TestBookingResponse, owner)

    booking = await find_booking(db, clinic_id, booking_id)
    if booking is None:
        return cast(
            TestBookingResponse,
            error_response(404, "BOOKING_NOT_FOUND", "Booking was not found."),
        )

    before = booking_snapshot(booking)
    booking.status = "cancelled"
    booking.deleted_at = now_ist()
    booking.deleted_by = None
    await db.commit()
    await db.refresh(booking, ["patient", "test"])
    await write_booking_audit(db, booking, "test_booking.deleted", before)
    return TestBookingResponse(data=booking_data(booking))


async def authorize_request(
    db: AsyncSession,
    authorization: str | None,
    clinic_id: str,
) -> CurrentOwner | JSONResponse:
    owner = authenticate_owner(authorization, clinic_id)
    if isinstance(owner, JSONResponse):
        return owner
    clinic = await find_owner_clinic(db, clinic_id, owner)
    if clinic is None:
        return error_response(404, "CLINIC_NOT_FOUND", "Clinic was not found.")
    await set_tenant_context(db, clinic_id)
    return owner


async def find_owner_clinic(db: AsyncSession, clinic_id: str, owner: CurrentOwner) -> Clinic | None:
    statement = select(Clinic).where(
        Clinic.id == clinic_id,
        Clinic.owner_whatsapp == owner.owner_whatsapp,
        Clinic.deleted_at.is_(None),
    )
    return (await db.execute(statement)).scalar_one_or_none()


def booking_filters(
    clinic_id: str,
    status: BookingStatus | None,
    booking_type: BookingType | None,
) -> list[ColumnElement[bool]]:
    filters: list[ColumnElement[bool]] = [
        TestBooking.clinic_id == clinic_id,
        TestBooking.deleted_at.is_(None),
    ]
    if status is not None:
        filters.append(TestBooking.status == status)
    if booking_type is not None:
        filters.append(TestBooking.booking_type == booking_type)
    return filters


async def count_bookings(db: AsyncSession, filters: list[ColumnElement[bool]]) -> int:
    statement = select(func.count()).select_from(TestBooking).where(*filters)
    return int((await db.execute(statement)).scalar_one())


async def find_patient(db: AsyncSession, clinic_id: str, patient_id: str) -> Patient | None:
    statement = select(Patient).where(
        Patient.clinic_id == clinic_id,
        Patient.id == patient_id,
        Patient.deleted_at.is_(None),
    )
    return (await db.execute(statement)).scalar_one_or_none()


async def find_test(db: AsyncSession, clinic_id: str, test_id: str | None) -> Test | None:
    statement = select(Test).where(
        Test.clinic_id == clinic_id,
        Test.id == test_id,
        Test.is_active.is_(True),
        Test.deleted_at.is_(None),
    )
    return (await db.execute(statement)).scalar_one_or_none()


async def find_booking(db: AsyncSession, clinic_id: str, booking_id: str) -> TestBooking | None:
    statement = select(TestBooking).where(
        TestBooking.clinic_id == clinic_id,
        TestBooking.id == booking_id,
        TestBooking.deleted_at.is_(None),
    )
    return (await db.execute(statement)).scalar_one_or_none()


def build_booking(
    clinic_id: str,
    payload: TestBookingCreateRequest,
    patient: Patient,
    test: Test | None,
) -> TestBooking:
    return TestBooking(
        clinic_id=clinic_id,
        patient_id=patient.id,
        test_id=test.id if test else None,
        test_name=test.name if test else cast(str, payload.test_name),
        booking_type=payload.booking_type,
        collection_address=payload.collection_address,
        collection_slot=payload.collection_slot,
        technician_name=payload.technician_name,
        amount=test.price if test and payload.amount is None else payload.amount,
        payment_status=payload.payment_status,
        payment_method=payload.payment_method,
        notes=payload.notes,
    )


def apply_booking_update(booking: TestBooking, payload: TestBookingUpdateRequest) -> None:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(booking, field, value)


async def write_booking_audit(
    db: AsyncSession,
    booking: TestBooking,
    action: str,
    before: dict[str, object] | None,
) -> None:
    await write_audit(
        db=db,
        clinic_id=booking.clinic_id,
        actor_type="owner",
        action=action,
        entity_type="test_booking",
        entity_id=booking.id if isinstance(booking.id, UUID) else None,
        diff={"before": before, "after": booking_snapshot(booking)},
    )


def booking_data(booking: TestBooking) -> TestBookingData:
    return TestBookingData(
        id=str(booking.id),
        patient_id=str(booking.patient_id),
        patient_name=booking.patient.name,
        patient_whatsapp=booking.patient.whatsapp_number,
        test_id=str(booking.test_id) if booking.test_id else None,
        test_name=booking.test_name,
        booking_type=cast(BookingType, booking.booking_type),
        status=cast(BookingStatus, booking.status),
        collection_address=booking.collection_address,
        collection_slot=booking.collection_slot,
        technician_name=booking.technician_name,
        amount=booking.amount,
        payment_status=cast(PaymentStatus, booking.payment_status),
        payment_method=booking.payment_method,
        report_file_path=booking.report_file_path,
        report_delivered_at=booking.report_delivered_at,
        booked_at=booking.booked_at,
        notes=booking.notes,
    )


def booking_snapshot(booking: TestBooking) -> dict[str, object]:
    return {
        "id": str(booking.id),
        "patient_id": str(booking.patient_id),
        "test_id": str(booking.test_id) if booking.test_id else None,
        "test_name": booking.test_name,
        "booking_type": booking.booking_type,
        "status": booking.status,
        "collection_address": booking.collection_address,
        "collection_slot": booking.collection_slot.isoformat() if booking.collection_slot else None,
        "technician_name": booking.technician_name,
        "amount": str(booking.amount) if booking.amount is not None else None,
        "payment_status": booking.payment_status,
        "payment_method": booking.payment_method,
        "report_file_path": booking.report_file_path,
        "report_delivered_at": (
            booking.report_delivered_at.isoformat() if booking.report_delivered_at else None
        ),
        "booked_at": booking.booked_at.isoformat() if booking.booked_at else None,
        "deleted_at": booking.deleted_at.isoformat() if booking.deleted_at else None,
        "notes": booking.notes,
    }
