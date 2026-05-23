from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.flows.base_flow import FlowMessage
from app.models import ConversationSession, Patient, TestBooking
from app.services.audit import write_audit
from app.services.cache import session_to_dict, update_session_cache
from app.templates.hinglish import (
    CANCEL_BOOKING_CONFIRMED,
    CANCEL_BOOKING_NOT_FOUND,
    REPORT_STATUS_NOT_FOUND,
    render_report_status_pending,
    render_report_status_ready,
)
from app.utils.datetime_utils import now_ist

REPORT_INQUIRY_FLOW = "report_inquiry"
CANCELLATION_FLOW = "cancel"
LOOKUP_REPORT = "lookup_report"
CANCEL_BOOKING = "cancel_booking"
REPORT_INQUIRY_COMPLETE = "report_inquiry_complete"
CANCELLATION_COMPLETE = "cancellation_complete"
CANCELLABLE_STATUSES = {"booked"}


class ReportInquiryFlow:
    async def handle(
        self,
        session: ConversationSession | None,
        message: FlowMessage,
        db: AsyncSession,
    ) -> str:
        session = await ensure_session(session, message, db, REPORT_INQUIRY_FLOW, LOOKUP_REPORT)
        patient_id = await resolve_patient_id(session, message, db)
        booking = await find_latest_booking(message, db, patient_id)

        finish_session(session, REPORT_INQUIRY_COMPLETE)
        await persist_session(session, message, db)

        if booking is None:
            return REPORT_STATUS_NOT_FOUND
        if booking.status in {"report_ready", "delivered"} or booking.report_file_path:
            return render_report_status_ready(booking.test_name)
        return render_report_status_pending(booking.test_name, booking.status)


class CancellationFlow:
    async def handle(
        self,
        session: ConversationSession | None,
        message: FlowMessage,
        db: AsyncSession,
    ) -> str:
        session = await ensure_session(session, message, db, CANCELLATION_FLOW, CANCEL_BOOKING)
        patient_id = await resolve_patient_id(session, message, db)
        booking = await find_latest_cancellable_booking(message, db, patient_id)

        if booking is None:
            finish_session(session, CANCELLATION_COMPLETE)
            await persist_session(session, message, db)
            return CANCEL_BOOKING_NOT_FOUND

        before_status = booking.status
        booking.status = "cancelled"
        booking.deleted_at = now_ist()
        booking.deleted_by = patient_id
        finish_session(session, CANCELLATION_COMPLETE)
        await db.commit()
        await write_cancellation_audit(db, message, booking, patient_id, before_status)
        await update_session_cache(
            message.whatsapp_number,
            str(message.clinic_id),
            session_to_dict(session),
        )
        return CANCEL_BOOKING_CONFIRMED.format(test_name=booking.test_name)


async def ensure_session(
    session: ConversationSession | None,
    message: FlowMessage,
    db: AsyncSession,
    flow: str,
    step: str,
) -> ConversationSession:
    if session is None:
        session = await find_session(message, db)

    if session is None:
        patient = await find_patient(message, db)
        session = ConversationSession(
            clinic_id=str(message.clinic_id),
            patient_id=patient.id if patient is not None else None,
            whatsapp_number=message.whatsapp_number,
            flow=flow,
            step=step,
            context={},
        )
        db.add(session)
    else:
        session.flow = flow
        session.step = session.step or step
        session.is_active = True

    await persist_session(session, message, db)
    return session


async def find_session(message: FlowMessage, db: AsyncSession) -> ConversationSession | None:
    statement = select(ConversationSession).where(
        ConversationSession.clinic_id == message.clinic_id,
        ConversationSession.whatsapp_number == message.whatsapp_number,
    )
    return (await db.execute(statement)).scalar_one_or_none()


async def find_patient(message: FlowMessage, db: AsyncSession) -> Patient | None:
    statement = select(Patient).where(
        Patient.clinic_id == message.clinic_id,
        Patient.whatsapp_number == message.whatsapp_number,
        Patient.deleted_at.is_(None),
    )
    return (await db.execute(statement)).scalar_one_or_none()


async def resolve_patient_id(
    session: ConversationSession,
    message: FlowMessage,
    db: AsyncSession,
) -> UUID | None:
    if session.patient_id is not None:
        return session.patient_id
    patient = await find_patient(message, db)
    if patient is None:
        return None
    session.patient_id = patient.id
    return patient.id


async def find_latest_booking(
    message: FlowMessage,
    db: AsyncSession,
    patient_id: UUID | None,
) -> TestBooking | None:
    if patient_id is None:
        return None
    statement = (
        select(TestBooking)
        .where(
            TestBooking.clinic_id == message.clinic_id,
            TestBooking.patient_id == patient_id,
            TestBooking.deleted_at.is_(None),
        )
        .order_by(TestBooking.created_at.desc())
        .limit(1)
    )
    return (await db.execute(statement)).scalar_one_or_none()


async def find_latest_cancellable_booking(
    message: FlowMessage,
    db: AsyncSession,
    patient_id: UUID | None,
) -> TestBooking | None:
    if patient_id is None:
        return None
    statement = (
        select(TestBooking)
        .where(
            TestBooking.clinic_id == message.clinic_id,
            TestBooking.patient_id == patient_id,
            TestBooking.status.in_(CANCELLABLE_STATUSES),
            TestBooking.deleted_at.is_(None),
        )
        .order_by(TestBooking.created_at.desc())
        .limit(1)
    )
    return (await db.execute(statement)).scalar_one_or_none()


def finish_session(session: ConversationSession, step: str) -> None:
    session.step = step
    session.is_active = False


async def persist_session(
    session: ConversationSession,
    message: FlowMessage,
    db: AsyncSession,
) -> None:
    now = now_ist()
    session.last_message_at = now
    session.expires_at = now + timedelta(minutes=30)
    await db.commit()
    await update_session_cache(
        message.whatsapp_number,
        str(message.clinic_id),
        session_to_dict(session),
    )


async def write_cancellation_audit(
    db: AsyncSession,
    message: FlowMessage,
    booking: TestBooking,
    patient_id: UUID | None,
    before_status: str,
) -> None:
    await write_audit(
        db=db,
        clinic_id=message.clinic_id,
        actor_id=patient_id,
        actor_type="patient",
        action="test_booking.cancelled",
        entity_type="test_booking",
        entity_id=booking.id if isinstance(booking.id, UUID) else None,
        diff={"before": {"status": before_status}, "after": {"status": booking.status}},
    )
