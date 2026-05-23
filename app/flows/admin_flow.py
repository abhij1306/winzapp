from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import timedelta
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.whatsapp_sender as whatsapp_sender
from app.config import get_settings
from app.flows.base_flow import FlowMessage
from app.models import ConversationSession, Patient, TestBooking
from app.services.audit import write_audit
from app.services.cache import get_clinic_by_id_cached
from app.templates.hinglish import (
    ADMIN_PATIENT_OPTED_OUT,
    ADMIN_REPORT_NOT_FOUND,
    ADMIN_REPORT_SENT,
    ADMIN_UNAUTHORIZED,
    ADMIN_UNKNOWN_COMMAND,
    CANCEL_BOOKING_CONFIRMED,
    CANCEL_BOOKING_NOT_FOUND,
    BookingSummary,
    render_admin_daily_stats,
    render_admin_pending_reports,
    render_admin_today_bookings,
)
from app.utils.datetime_utils import now_ist

PENDING_REPORT_STATUSES = {"sample_collected", "processing", "report_ready"}
UUID_PATTERN = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
)


class AdminFlow:
    async def handle(
        self,
        session: ConversationSession | None,
        message: FlowMessage,
        db: AsyncSession,
    ) -> str:
        clinic = await get_clinic_by_id_cached(str(message.clinic_id), db)
        if not is_owner_message(clinic, message):
            return ADMIN_UNAUTHORIZED

        text = normalize(message.text)
        if is_today_command(text):
            return render_admin_today_bookings(
                cast(Sequence[BookingSummary], await get_today_bookings(message, db)),
            )
        if is_pending_reports_command(text):
            return render_admin_pending_reports(
                cast(Sequence[BookingSummary], await get_pending_reports(message, db)),
            )
        if is_send_report_command(text):
            return await handle_send_report(message, db, clinic)
        if is_cancel_command(text):
            return await handle_cancel_booking(message, db)
        if is_daily_stats_command(text):
            return render_admin_daily_stats(await get_daily_stats(message, db))
        return ADMIN_UNKNOWN_COMMAND


def is_owner_message(clinic: dict[str, object] | None, message: FlowMessage) -> bool:
    return clinic is not None and clinic.get("owner_whatsapp") == message.whatsapp_number


def normalize(value: str) -> str:
    return " ".join(value.lower().split())


def is_today_command(text: str) -> bool:
    return ("aaj" in text or "today" in text) and ("test" in text or "booking" in text)


def is_pending_reports_command(text: str) -> bool:
    return "pending" in text and "report" in text


def is_send_report_command(text: str) -> bool:
    return "send" in text and "report" in text


def is_cancel_command(text: str) -> bool:
    return "cancel" in text and "booking" in text


def is_daily_stats_command(text: str) -> bool:
    return "stats" in text or "daily" in text or "digest" in text


async def get_today_bookings(
    message: FlowMessage,
    db: AsyncSession,
) -> list[TestBooking]:
    start, end = today_bounds()
    statement = (
        select(TestBooking)
        .where(
            TestBooking.clinic_id == message.clinic_id,
            TestBooking.booked_at >= start,
            TestBooking.booked_at < end,
            TestBooking.deleted_at.is_(None),
        )
        .order_by(TestBooking.booked_at, TestBooking.test_name, TestBooking.created_at)
    )
    return list((await db.execute(statement)).scalars().all())


async def get_pending_reports(
    message: FlowMessage,
    db: AsyncSession,
) -> list[TestBooking]:
    statement = (
        select(TestBooking)
        .where(
            TestBooking.clinic_id == message.clinic_id,
            TestBooking.status.in_(PENDING_REPORT_STATUSES),
            TestBooking.report_delivered_at.is_(None),
            TestBooking.deleted_at.is_(None),
        )
        .order_by(TestBooking.booked_at, TestBooking.test_name, TestBooking.created_at)
    )
    return list((await db.execute(statement)).scalars().all())


async def handle_send_report(
    message: FlowMessage,
    db: AsyncSession,
    clinic: dict[str, object] | None,
) -> str:
    booking_id = extract_uuid(message.text)
    booking = await find_report_ready_booking(message, db, booking_id)
    if booking is None or not booking.report_file_path:
        return ADMIN_REPORT_NOT_FOUND

    patient = await find_patient_by_id(message, db, booking.patient_id)
    if patient is None:
        return ADMIN_REPORT_NOT_FOUND
    if not patient.opt_in:
        return ADMIN_PATIENT_OPTED_OUT

    await send_report_document(clinic, patient, booking)
    booking.status = "delivered"
    booking.report_delivered_at = now_ist()
    booking.report_status_notified = True
    await db.commit()
    await write_report_audit(db, message, booking)
    return ADMIN_REPORT_SENT.format(test_name=booking.test_name)


async def handle_cancel_booking(
    message: FlowMessage,
    db: AsyncSession,
) -> str:
    booking_id = extract_uuid(message.text)
    booking = await find_active_booking(message, db, booking_id)
    if booking is None:
        return CANCEL_BOOKING_NOT_FOUND

    before_status = booking.status
    booking.status = "cancelled"
    booking.deleted_at = now_ist()
    await db.commit()
    await write_cancel_audit(db, message, booking, before_status)
    return CANCEL_BOOKING_CONFIRMED.format(test_name=booking.test_name)


async def get_daily_stats(
    message: FlowMessage,
    db: AsyncSession,
) -> dict[str, int]:
    today_bookings = await get_today_bookings(message, db)
    pending_reports = await get_pending_reports(message, db)
    delivered_today = await get_delivered_reports_today(message, db)
    return {
        "bookings_today": len(today_bookings),
        "home_collection_today": count_booking_type(today_bookings, "home_collection"),
        "walkin_today": count_booking_type(today_bookings, "walkin"),
        "pending_reports": len(pending_reports),
        "reports_delivered_today": delivered_today,
    }


async def get_delivered_reports_today(message: FlowMessage, db: AsyncSession) -> int:
    start, end = today_bounds()
    statement = select(TestBooking).where(
        TestBooking.clinic_id == message.clinic_id,
        TestBooking.report_delivered_at >= start,
        TestBooking.report_delivered_at < end,
        TestBooking.deleted_at.is_(None),
    )
    return len((await db.execute(statement)).scalars().all())


async def find_report_ready_booking(
    message: FlowMessage,
    db: AsyncSession,
    booking_id: UUID | None,
) -> TestBooking | None:
    if booking_id is None:
        return None
    statement = select(TestBooking).where(
        TestBooking.clinic_id == message.clinic_id,
        TestBooking.id == booking_id,
        TestBooking.status == "report_ready",
        TestBooking.deleted_at.is_(None),
    )
    return (await db.execute(statement)).scalar_one_or_none()


async def find_active_booking(
    message: FlowMessage,
    db: AsyncSession,
    booking_id: UUID | None,
) -> TestBooking | None:
    if booking_id is None:
        return None
    statement = select(TestBooking).where(
        TestBooking.clinic_id == message.clinic_id,
        TestBooking.id == booking_id,
        TestBooking.deleted_at.is_(None),
    )
    return (await db.execute(statement)).scalar_one_or_none()


async def find_patient_by_id(
    message: FlowMessage,
    db: AsyncSession,
    patient_id: str,
) -> Patient | None:
    statement = select(Patient).where(
        Patient.clinic_id == message.clinic_id,
        Patient.id == patient_id,
        Patient.deleted_at.is_(None),
    )
    return (await db.execute(statement)).scalar_one_or_none()


async def send_report_document(
    clinic: dict[str, object] | None,
    patient: Patient,
    booking: TestBooking,
) -> None:
    settings = get_settings()
    await whatsapp_sender.send_document(
        phone_number_id=clinic_phone_number_id(clinic),
        to=patient.whatsapp_number,
        access_token=settings.wa_access_token,
        document_url=cast(str, booking.report_file_path),
        filename=f"{booking.test_name}_report.pdf",
        caption=f"{booking.test_name} report attached hai.",
    )


async def write_report_audit(
    db: AsyncSession,
    message: FlowMessage,
    booking: TestBooking,
) -> None:
    await write_audit(
        db=db,
        clinic_id=message.clinic_id,
        actor_type="owner",
        action="report.delivered",
        entity_type="test_booking",
        entity_id=booking.id if isinstance(booking.id, UUID) else None,
        diff={"status": booking.status, "report_status_notified": True},
    )


async def write_cancel_audit(
    db: AsyncSession,
    message: FlowMessage,
    booking: TestBooking,
    before_status: str,
) -> None:
    await write_audit(
        db=db,
        clinic_id=message.clinic_id,
        actor_type="owner",
        action="test_booking.cancelled",
        entity_type="test_booking",
        entity_id=booking.id if isinstance(booking.id, UUID) else None,
        diff={"before": {"status": before_status}, "after": {"status": booking.status}},
    )


def today_bounds() -> tuple[object, object]:
    start = now_ist().replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def count_booking_type(bookings: Sequence[TestBooking], booking_type: str) -> int:
    return sum(1 for booking in bookings if booking.booking_type == booking_type)


def extract_uuid(value: str) -> UUID | None:
    match = UUID_PATTERN.search(value)
    if match is None:
        return None
    return UUID(match.group(0))


def clinic_phone_number_id(clinic: dict[str, object] | None) -> str:
    if clinic is None:
        return ""
    settings = clinic.get("settings")
    if isinstance(settings, dict):
        return str(settings.get("wa_phone_number_id") or "")
    return ""
