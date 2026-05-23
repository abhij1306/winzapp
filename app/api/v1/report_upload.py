from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, File, Header, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.storage as storage
import app.services.whatsapp_sender as whatsapp_sender
from app.api.errors import error_response
from app.api.v1.report_ready import clinic_phone_number_id
from app.api.v1.test_bookings import authorize_request, booking_snapshot, find_booking
from app.config import get_settings
from app.database import get_db
from app.models import TestBooking
from app.schemas.report_ready import ReportReadyData, ReportReadyResponse
from app.services.audit import write_audit
from app.services.cache import get_clinic_by_id_cached
from app.services.recall_scheduling import maybe_create_recall_for_booking
from app.templates.hinglish import REPORT_DELIVERY_CAPTION
from app.utils.datetime_utils import now_ist

router = APIRouter(prefix="/clinics/{clinic_id}/test-bookings", tags=["reports"])


@router.post("/{booking_id}/report-upload", response_model=ReportReadyResponse)
async def upload_report(
    clinic_id: str,
    booking_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    report_pdf: Annotated[UploadFile, File()],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> ReportReadyResponse:
    owner = await authorize_request(db, authorization, clinic_id)
    if isinstance(owner, JSONResponse):
        return cast(ReportReadyResponse, owner)

    booking = await find_booking(db, clinic_id, booking_id)
    if booking is None:
        return cast(
            ReportReadyResponse,
            error_response(404, "BOOKING_NOT_FOUND", "Booking was not found."),
        )
    if not is_pdf_upload(report_pdf):
        return invalid_pdf_response()

    pdf_bytes = await report_pdf.read()
    if not pdf_bytes.startswith(b"%PDF"):
        return invalid_pdf_response()

    stored_path = await storage.upload_report_pdf(pdf_bytes, clinic_id, booking_id)
    signed_url = await storage.create_signed_url(stored_path, expires_in=86400)
    clinic = await get_clinic_by_id_cached(clinic_id, db)
    await send_uploaded_report(clinic, booking, signed_url)
    await mark_report_uploaded(db, booking, stored_path)
    await maybe_create_recall_for_booking(db, booking)
    return ReportReadyResponse(
        data=ReportReadyData(
            booking_id=str(booking.id),
            status=booking.status,
            report_file_path=stored_path,
        ),
    )


def is_pdf_upload(report_pdf: UploadFile) -> bool:
    filename = report_pdf.filename or ""
    return report_pdf.content_type == "application/pdf" and filename.lower().endswith(".pdf")


def invalid_pdf_response() -> ReportReadyResponse:
    return cast(
        ReportReadyResponse,
        error_response(400, "REPORT_FILE_INVALID", "Upload a valid PDF report file."),
    )


async def send_uploaded_report(
    clinic: dict[str, object] | None,
    booking: TestBooking,
    signed_url: str,
) -> None:
    settings = get_settings()
    await whatsapp_sender.send_document(
        phone_number_id=clinic_phone_number_id(clinic),
        to=booking.patient.whatsapp_number,
        access_token=settings.wa_access_token,
        document_url=signed_url,
        filename=f"Report_{booking.test_name}.pdf",
        caption=REPORT_DELIVERY_CAPTION.format(test_name=booking.test_name),
    )


async def mark_report_uploaded(
    db: AsyncSession,
    booking: TestBooking,
    stored_path: str,
) -> None:
    before = booking_snapshot(booking)
    booking.status = "delivered"
    booking.report_file_path = stored_path
    booking.report_delivered_at = now_ist()
    booking.report_status_notified = True
    await db.commit()
    await write_audit(
        db=db,
        clinic_id=booking.clinic_id,
        actor_type="owner",
        action="report.delivered",
        entity_type="test_booking",
        entity_id=booking.id if isinstance(booking.id, UUID) else None,
        diff={"before": before, "after": booking_snapshot(booking)},
    )
