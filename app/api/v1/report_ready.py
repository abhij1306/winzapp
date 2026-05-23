from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.storage as storage
import app.services.whatsapp_sender as whatsapp_sender
from app.api.errors import error_response
from app.config import get_settings
from app.database import get_db
from app.models import Patient, TestBooking
from app.schemas.report_ready import ReportReadyData, ReportReadyRequest, ReportReadyResponse
from app.services.audit import write_audit
from app.services.cache import get_clinic_by_id_cached
from app.services.recall_scheduling import maybe_create_recall_for_booking
from app.templates.hinglish import REPORT_DELIVERY_CAPTION
from app.utils.datetime_utils import now_ist

router = APIRouter(tags=["reports"])


@router.post("/report-ready", response_model=ReportReadyResponse)
async def report_ready(
    payload: ReportReadyRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReportReadyResponse:
    match = await find_report_booking(payload, db)
    if match is None:
        return cast(
            ReportReadyResponse,
            error_response(404, "REPORT_BOOKING_NOT_FOUND", "Matching test booking was not found."),
        )

    patient, booking = match
    clinic = await get_clinic_by_id_cached(payload.clinic_id, db)
    stored_path = await store_report(payload, booking)
    signed_url = await storage.create_signed_url(stored_path, expires_in=86400)
    await send_report_document(clinic, patient, booking, signed_url)
    await mark_report_delivered(db, payload.clinic_id, booking, stored_path)
    await maybe_create_recall_for_booking(db, booking)
    return ReportReadyResponse(
        data=ReportReadyData(
            booking_id=str(booking.id),
            status=booking.status,
            report_file_path=stored_path,
        ),
    )


async def find_report_booking(
    payload: ReportReadyRequest,
    db: AsyncSession,
) -> tuple[Patient, TestBooking] | None:
    patient = await find_patient(payload, db)
    if patient is None:
        return None
    statement = (
        select(TestBooking)
        .where(
            TestBooking.clinic_id == payload.clinic_id,
            TestBooking.patient_id == patient.id,
            TestBooking.test_name == payload.test_name,
            TestBooking.status.notin_(("delivered", "cancelled")),
            TestBooking.deleted_at.is_(None),
        )
        .order_by(TestBooking.created_at.desc())
        .limit(1)
    )
    booking = (await db.execute(statement)).scalar_one_or_none()
    if booking is None:
        return None
    return patient, booking


async def find_patient(payload: ReportReadyRequest, db: AsyncSession) -> Patient | None:
    statement = select(Patient).where(
        Patient.clinic_id == payload.clinic_id,
        Patient.whatsapp_number == payload.patient_phone,
        Patient.deleted_at.is_(None),
    )
    return (await db.execute(statement)).scalar_one_or_none()


async def store_report(payload: ReportReadyRequest, booking: TestBooking) -> str:
    booking_id = str(booking.id)
    if payload.report_pdf_url:
        return await storage.copy_report_from_url(
            payload.report_pdf_url,
            payload.clinic_id,
            booking_id,
        )
    return await storage.upload_report_base64(
        cast(str, payload.report_pdf_base64),
        payload.clinic_id,
        booking_id,
    )


async def send_report_document(
    clinic: dict[str, object] | None,
    patient: Patient,
    booking: TestBooking,
    signed_url: str,
) -> None:
    settings = get_settings()
    await whatsapp_sender.send_document(
        phone_number_id=clinic_phone_number_id(clinic),
        to=patient.whatsapp_number,
        access_token=settings.wa_access_token,
        document_url=signed_url,
        filename=f"Report_{booking.test_name}.pdf",
        caption=REPORT_DELIVERY_CAPTION.format(test_name=booking.test_name),
    )


async def mark_report_delivered(
    db: AsyncSession,
    clinic_id: str,
    booking: TestBooking,
    stored_path: str,
) -> None:
    booking.status = "delivered"
    booking.report_file_path = stored_path
    booking.report_delivered_at = now_ist()
    booking.report_status_notified = True
    await db.commit()
    await write_audit(
        db=db,
        clinic_id=clinic_id,
        actor_type="system",
        action="report.delivered",
        entity_type="test_booking",
        entity_id=booking.id if isinstance(booking.id, UUID) else None,
        diff={"status": booking.status, "report_file_path": stored_path},
    )


def clinic_phone_number_id(clinic: dict[str, object] | None) -> str:
    if clinic is None:
        return ""
    settings = clinic.get("settings")
    if isinstance(settings, dict):
        return str(settings.get("wa_phone_number_id") or "")
    return ""
