from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.whatsapp_sender as whatsapp_sender
from app.config import get_settings
from app.database import SessionLocal
from app.flows.admin_flow import PENDING_REPORT_STATUSES
from app.models import Clinic, Patient, RecallSchedule, Test, TestBooking
from app.services.cache import redis_set_json
from app.utils.datetime_utils import now_ist

HEARTBEAT_KEY = "scheduler:heartbeat"
TEMPLATE_LANGUAGE = "en_US"
REVIEW_SENT_MARKER = "review_request_sent=true"


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=ZoneInfo("Asia/Kolkata"))
    scheduler.add_job(run_fasting_reminders_job, "cron", hour=20, minute=0, id="fasting-reminders")
    scheduler.add_job(run_review_requests_job, "cron", hour=18, minute=0, id="review-requests")
    scheduler.add_job(run_recall_reminders_job, "cron", hour=9, minute=30, id="recall-reminders")
    scheduler.add_job(run_daily_digest_job, "cron", hour=9, minute=0, id="daily-digest")
    scheduler.add_job(run_scheduler_heartbeat_job, "interval", minutes=1, id="scheduler-heartbeat")
    return scheduler


async def run_fasting_reminders_job() -> None:
    async with SessionLocal() as db:
        await send_fasting_reminders(db)


async def run_review_requests_job() -> None:
    async with SessionLocal() as db:
        await send_review_requests(db)


async def run_recall_reminders_job() -> None:
    async with SessionLocal() as db:
        await send_recall_reminders(db)


async def run_daily_digest_job() -> None:
    async with SessionLocal() as db:
        await send_daily_digests(db)


async def run_scheduler_heartbeat_job() -> None:
    await write_scheduler_heartbeat()


async def send_fasting_reminders(db: AsyncSession) -> int:
    due_until = now_ist() + timedelta(days=1)
    statement = (
        select(TestBooking)
        .join(TestBooking.patient)
        .join(TestBooking.test)
        .join(TestBooking.clinic)
        .where(
            TestBooking.clinic_id == Clinic.id,
            TestBooking.patient_id == Patient.id,
            TestBooking.test_id == Test.id,
            TestBooking.collection_slot.is_not(None),
            TestBooking.collection_slot <= due_until,
            TestBooking.status.in_(("booked", "sample_collected")),
            TestBooking.fasting_reminder_sent.is_(False),
            TestBooking.deleted_at.is_(None),
            Test.requires_fasting.is_(True),
            Patient.opt_in.is_(True),
        )
        .order_by(TestBooking.collection_slot, TestBooking.created_at)
    )
    bookings = list((await db.execute(statement)).scalars().all())
    for booking in bookings:
        await send_booking_template(booking, "fasting_reminder", fasting_components(booking))
        booking.fasting_reminder_sent = True
    await db.commit()
    return len(bookings)


async def send_recall_reminders(db: AsyncSession) -> int:
    statement = (
        select(RecallSchedule)
        .join(RecallSchedule.patient)
        .join(RecallSchedule.clinic)
        .where(
            RecallSchedule.trigger_at <= now_ist(),
            RecallSchedule.status == "pending",
            Patient.opt_in.is_(True),
        )
        .order_by(RecallSchedule.trigger_at, RecallSchedule.created_at)
    )
    recalls = list((await db.execute(statement)).scalars().all())
    for recall in recalls:
        await send_patient_template(
            recall.clinic,
            recall.patient,
            recall.message_template or "recall_reminder",
            recall_components(recall),
        )
        recall.status = "sent"
        recall.sent_at = now_ist()
    await db.commit()
    return len(recalls)


async def send_review_requests(db: AsyncSession) -> int:
    statement = (
        select(TestBooking)
        .join(TestBooking.patient)
        .join(TestBooking.clinic)
        .where(
            TestBooking.status == "delivered",
            TestBooking.report_delivered_at.is_not(None),
            TestBooking.deleted_at.is_(None),
            Patient.opt_in.is_(True),
            Clinic.gbp_review_link.is_not(None),
            or_(TestBooking.notes.is_(None), ~TestBooking.notes.ilike(f"%{REVIEW_SENT_MARKER}%")),
        )
        .order_by(TestBooking.report_delivered_at, TestBooking.created_at)
    )
    bookings = list((await db.execute(statement)).scalars().all())
    for booking in bookings:
        await send_booking_template(booking, "review_request", review_components(booking))
        booking.notes = append_note_marker(booking.notes, REVIEW_SENT_MARKER)
    await db.commit()
    return len(bookings)


async def send_daily_digests(db: AsyncSession) -> int:
    clinics = list(
        (
            await db.execute(
                select(Clinic).where(
                    Clinic.deleted_at.is_(None),
                    Clinic.owner_whatsapp.is_not(None),
                ),
            )
        )
        .scalars()
        .all(),
    )
    for clinic in clinics:
        stats = await daily_stats(db, str(clinic.id))
        await whatsapp_sender.send_template(
            phone_number_id=clinic_phone_number_id(clinic),
            to=clinic.owner_whatsapp,
            access_token=get_settings().wa_access_token,
            template_name="daily_digest",
            language_code=TEMPLATE_LANGUAGE,
            components=text_components(render_daily_digest(stats)),
        )
    return len(clinics)


async def write_scheduler_heartbeat() -> None:
    await redis_set_json(HEARTBEAT_KEY, 5 * 60, {"seen_at": now_ist().isoformat()})


async def daily_stats(db: AsyncSession, clinic_id: str) -> dict[str, int]:
    start = now_ist().replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    bookings_today = await count_bookings_between(db, clinic_id, start, end)
    pending_reports = await count_pending_reports(db, clinic_id)
    delivered_today = await count_delivered_reports_between(db, clinic_id, start, end)
    return {
        "bookings_today": bookings_today,
        "pending_reports": pending_reports,
        "reports_delivered_today": delivered_today,
    }


async def count_bookings_between(
    db: AsyncSession,
    clinic_id: str,
    start: object,
    end: object,
) -> int:
    statement = select(func.count()).select_from(TestBooking).where(
        TestBooking.clinic_id == clinic_id,
        TestBooking.booked_at >= start,
        TestBooking.booked_at < end,
        TestBooking.deleted_at.is_(None),
    )
    return int((await db.execute(statement)).scalar_one())


async def count_pending_reports(db: AsyncSession, clinic_id: str) -> int:
    statement = select(func.count()).select_from(TestBooking).where(
        TestBooking.clinic_id == clinic_id,
        TestBooking.status.in_(PENDING_REPORT_STATUSES),
        TestBooking.report_delivered_at.is_(None),
        TestBooking.deleted_at.is_(None),
    )
    return int((await db.execute(statement)).scalar_one())


async def count_delivered_reports_between(
    db: AsyncSession,
    clinic_id: str,
    start: object,
    end: object,
) -> int:
    statement = select(func.count()).select_from(TestBooking).where(
        TestBooking.clinic_id == clinic_id,
        TestBooking.report_delivered_at >= start,
        TestBooking.report_delivered_at < end,
        TestBooking.deleted_at.is_(None),
    )
    return int((await db.execute(statement)).scalar_one())


async def send_booking_template(
    booking: TestBooking,
    template_name: str,
    components: list[dict[str, object]] | None = None,
) -> None:
    await send_patient_template(booking.clinic, booking.patient, template_name, components)


async def send_patient_template(
    clinic: Clinic,
    patient: Patient,
    template_name: str,
    components: list[dict[str, object]] | None = None,
) -> None:
    await whatsapp_sender.send_template(
        phone_number_id=clinic_phone_number_id(clinic),
        to=patient.whatsapp_number,
        access_token=get_settings().wa_access_token,
        template_name=template_name,
        language_code=TEMPLATE_LANGUAGE,
        components=components,
    )


def clinic_phone_number_id(clinic: Clinic) -> str:
    return str(clinic.settings.get("wa_phone_number_id") or "")


def fasting_components(booking: TestBooking) -> list[dict[str, object]]:
    return text_components(f"{booking.test_name} fasting reminder for clinic {booking.clinic_id}")


def recall_components(recall: RecallSchedule) -> list[dict[str, object]]:
    return text_components(f"{recall.trigger_type} recall")


def review_components(booking: TestBooking) -> list[dict[str, object]]:
    return text_components(str(booking.clinic.gbp_review_link or ""))


def text_components(text: str) -> list[dict[str, object]]:
    return [
        {
            "type": "body",
            "parameters": [{"type": "text", "text": text}],
        },
    ]


def render_daily_digest(stats: dict[str, int]) -> str:
    return (
        f"Tests booked today: {stats['bookings_today']}; "
        f"Pending reports: {stats['pending_reports']}; "
        f"Reports delivered today: {stats['reports_delivered_today']}"
    )


def append_note_marker(notes: str | None, marker: str) -> str:
    parts: Sequence[str] = () if not notes else (notes,)
    return "\n".join((*parts, marker))
