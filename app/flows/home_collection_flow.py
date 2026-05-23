from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.flows.base_flow import FlowMessage
from app.models import ConversationSession, Patient, TestBooking
from app.services.audit import write_audit
from app.services.cache import get_tests_cached, session_to_dict, update_session_cache
from app.services.feature_flags import require_feature
from app.templates.hinglish import (
    HOME_COLLECTION_CONFIRMED,
    HOME_COLLECTION_UNKNOWN_SLOT,
    HOME_COLLECTION_UNKNOWN_TEST,
    render_address_prompt,
    render_home_test_selection_prompt,
    render_morning_slot_prompt,
)
from app.utils.datetime_utils import now_ist

HOME_COLLECTION_FLOW = "home_collection"
SELECT_TEST = "select_test"
CAPTURE_ADDRESS = "capture_address"
SELECT_SLOT = "select_slot"
HOME_COLLECTION_COMPLETE = "home_collection_complete"


class HomeCollectionFlow:
    async def handle(
        self,
        session: ConversationSession | None,
        message: FlowMessage,
        db: AsyncSession,
    ) -> str:
        await require_feature(str(message.clinic_id), "home_collection", db)
        session = await ensure_home_collection_session(session, message, db)
        tests = await get_home_collection_tests(message, db)

        if session.step == SELECT_TEST:
            return await handle_test_step(session, message, db, tests)
        if session.step == CAPTURE_ADDRESS:
            return await handle_address_step(session, message, db)
        if session.step == SELECT_SLOT:
            return await handle_slot_step(session, message, db)

        session.step = SELECT_TEST
        await set_available_tests(session, message, db, tests)
        return render_home_test_selection_prompt(test_names(tests))


async def ensure_home_collection_session(
    session: ConversationSession | None,
    message: FlowMessage,
    db: AsyncSession,
) -> ConversationSession:
    if session is None:
        session = await find_active_session(message, db)

    if session is None:
        patient = await find_patient(message, db)
        session = ConversationSession(
            clinic_id=str(message.clinic_id),
            patient_id=patient.id if patient is not None else None,
            whatsapp_number=message.whatsapp_number,
            flow=HOME_COLLECTION_FLOW,
            step=SELECT_TEST,
            context={},
        )
        db.add(session)
    else:
        session.flow = HOME_COLLECTION_FLOW
        session.step = session.step or SELECT_TEST
        session.is_active = True

    await persist_session(session, message, db)
    return session


async def find_active_session(
    message: FlowMessage,
    db: AsyncSession,
) -> ConversationSession | None:
    statement = select(ConversationSession).where(
        ConversationSession.clinic_id == message.clinic_id,
        ConversationSession.whatsapp_number == message.whatsapp_number,
        ConversationSession.is_active.is_(True),
    )
    return (await db.execute(statement)).scalar_one_or_none()


async def find_patient(message: FlowMessage, db: AsyncSession) -> Patient | None:
    statement = select(Patient).where(
        Patient.clinic_id == message.clinic_id,
        Patient.whatsapp_number == message.whatsapp_number,
        Patient.deleted_at.is_(None),
    )
    return (await db.execute(statement)).scalar_one_or_none()


async def get_home_collection_tests(
    message: FlowMessage,
    db: AsyncSession,
) -> list[dict[str, object]]:
    tests = await get_tests_cached(str(message.clinic_id), db)
    return [item for item in tests if item.get("home_collection_available") is True]


async def set_available_tests(
    session: ConversationSession,
    message: FlowMessage,
    db: AsyncSession,
    tests: list[dict[str, object]],
) -> None:
    session.context = {"available_test_ids": [str(item["id"]) for item in tests]}
    await persist_session(session, message, db)


async def handle_test_step(
    session: ConversationSession,
    message: FlowMessage,
    db: AsyncSession,
    tests: list[dict[str, object]],
) -> str:
    if not session.context.get("available_test_ids"):
        await set_available_tests(session, message, db, tests)
        return render_home_test_selection_prompt(test_names(tests))

    selected = match_test(
        message.text,
        tests,
        ids_from_context(session.context["available_test_ids"]),
    )
    if selected is None:
        await persist_session(session, message, db)
        return HOME_COLLECTION_UNKNOWN_TEST

    requires_fasting = selected.get("requires_fasting") is True
    session.step = CAPTURE_ADDRESS
    session.context = {
        **session.context,
        "selected_test_id": str(selected["id"]),
        "selected_test_name": str(selected["name"]),
        "selected_test_price": str(selected.get("price") or "0.00"),
        "requires_fasting": requires_fasting,
    }
    await persist_session(session, message, db)
    return render_address_prompt(requires_fasting)


async def handle_address_step(
    session: ConversationSession,
    message: FlowMessage,
    db: AsyncSession,
) -> str:
    session.step = SELECT_SLOT
    session.context = {**session.context, "collection_address": message.text.strip()}
    await persist_session(session, message, db)
    return render_morning_slot_prompt()


async def handle_slot_step(
    session: ConversationSession,
    message: FlowMessage,
    db: AsyncSession,
) -> str:
    collection_slot = parse_slot_choice(message.text)
    if collection_slot is None:
        await persist_session(session, message, db)
        return HOME_COLLECTION_UNKNOWN_SLOT

    booking = create_home_collection_booking(session, message, collection_slot)
    db.add(booking)
    await db.flush()
    session.step = HOME_COLLECTION_COMPLETE
    session.is_active = False
    session.context = {**session.context, "booking_id": str(booking.id)}
    await db.commit()
    await write_booking_audit(db, message, booking)
    await update_session_cache(
        message.whatsapp_number,
        str(message.clinic_id),
        session_to_dict(session),
    )
    return HOME_COLLECTION_CONFIRMED.format(test_name=booking.test_name)


def create_home_collection_booking(
    session: ConversationSession,
    message: FlowMessage,
    collection_slot: datetime,
) -> TestBooking:
    requires_fasting = session.context.get("requires_fasting") is True
    return TestBooking(
        clinic_id=str(message.clinic_id),
        patient_id=str(session.patient_id),
        test_id=str(session.context["selected_test_id"]),
        test_name=str(session.context["selected_test_name"]),
        booking_type="home_collection",
        status="booked",
        collection_address=str(session.context["collection_address"]),
        collection_slot=collection_slot,
        amount=Decimal(str(session.context["selected_test_price"])),
        payment_status="pending",
        payment_method="manual_offline",
        notes="requires_fasting=true" if requires_fasting else "requires_fasting=false",
    )


async def write_booking_audit(
    db: AsyncSession,
    message: FlowMessage,
    booking: TestBooking,
) -> None:
    await write_audit(
        db=db,
        clinic_id=message.clinic_id,
        actor_type="patient",
        action="test_booking.created",
        entity_type="test_booking",
        entity_id=booking.id if isinstance(booking.id, UUID) else None,
        diff={
            "booking_type": booking.booking_type,
            "test_name": booking.test_name,
            "collection_address": booking.collection_address,
        },
    )


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


def test_names(tests: list[dict[str, object]]) -> list[str]:
    return [str(item["name"]) for item in tests]


def match_test(
    message_text: str,
    tests: list[dict[str, object]],
    available_ids: set[str],
) -> dict[str, object] | None:
    normalized = normalize(message_text)
    available = [item for item in tests if str(item.get("id")) in available_ids]
    for item in available:
        if normalize(str(item.get("name"))) == normalized:
            return item
    if normalized.isdigit():
        index = int(normalized) - 1
        if 0 <= index < len(available):
            return available[index]
    return None


def normalize(value: str) -> str:
    return " ".join(value.lower().split())


def ids_from_context(value: object) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {str(item) for item in value}


def parse_slot_choice(message_text: str) -> datetime | None:
    normalized = message_text.strip().lower()
    now = now_ist()
    tomorrow = now + timedelta(days=1)
    if normalized in {"1", "8", "8am", "8 am"}:
        return tomorrow.replace(hour=8, minute=0, second=0, microsecond=0)
    if normalized in {"2", "10", "10am", "10 am"}:
        return tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)
    return None
