from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RecallSchedule, TestBooking
from app.services.audit import write_audit
from app.services.cache import get_clinic_by_id_cached
from app.utils.datetime_utils import now_ist

RECALL_TEMPLATE_NAME = "recall_reminder"


@dataclass(frozen=True)
class RecallRule:
    trigger_type: str
    days_after_report: int


async def maybe_create_recall_for_booking(
    db: AsyncSession,
    booking: TestBooking,
) -> RecallSchedule | None:
    if not await recall_feature_enabled(db, str(booking.clinic_id)):
        return None

    rule = recall_rule_for_test(booking.test_name)
    if rule is None:
        return None

    existing = await find_existing_recall(db, booking, rule)
    if existing is not None:
        return existing

    recall = build_recall(booking, rule)
    db.add(recall)
    await db.commit()
    await write_recall_audit(db, booking, recall)
    return recall


async def recall_feature_enabled(db: AsyncSession, clinic_id: str) -> bool:
    clinic = await get_clinic_by_id_cached(clinic_id, db)
    if clinic is None:
        return False
    settings = clinic.get("settings")
    if not isinstance(settings, dict):
        return False
    features = settings.get("features")
    return isinstance(features, dict) and features.get("recall_automation") is True


def recall_rule_for_test(test_name: str) -> RecallRule | None:
    normalized = normalize(test_name)
    if "hba1c" in normalized or "diabetes" in normalized:
        return RecallRule(trigger_type="hba1c_quarterly", days_after_report=90)
    if "thyroid" in normalized or "tsh" in normalized:
        return RecallRule(trigger_type="thyroid_6month", days_after_report=180)
    if "full body" in normalized or "annual" in normalized or "health checkup" in normalized:
        return RecallRule(trigger_type="annual_checkup", days_after_report=365)
    if "lipid" in normalized:
        return RecallRule(trigger_type="lipid_annual", days_after_report=365)
    return None


async def find_existing_recall(
    db: AsyncSession,
    booking: TestBooking,
    rule: RecallRule,
) -> RecallSchedule | None:
    statement = select(RecallSchedule).where(
        RecallSchedule.clinic_id == booking.clinic_id,
        RecallSchedule.reference_id == booking.id,
        RecallSchedule.trigger_type == rule.trigger_type,
    )
    return (await db.execute(statement)).scalar_one_or_none()


def build_recall(booking: TestBooking, rule: RecallRule) -> RecallSchedule:
    base = booking.report_delivered_at or now_ist()
    return RecallSchedule(
        clinic_id=booking.clinic_id,
        patient_id=booking.patient_id,
        trigger_type=rule.trigger_type,
        trigger_at=base + timedelta(days=rule.days_after_report),
        message_template=RECALL_TEMPLATE_NAME,
        status="pending",
        reference_id=booking.id if isinstance(booking.id, UUID) else None,
    )


async def write_recall_audit(
    db: AsyncSession,
    booking: TestBooking,
    recall: RecallSchedule,
) -> None:
    await write_audit(
        db=db,
        clinic_id=booking.clinic_id,
        actor_type="system",
        action="recall.created",
        entity_type="recall_schedule",
        entity_id=recall.id if isinstance(recall.id, UUID) else None,
        diff={
            "trigger_type": recall.trigger_type,
            "reference_id": str(recall.reference_id),
        },
    )


def normalize(value: str) -> str:
    return " ".join(value.lower().split())
