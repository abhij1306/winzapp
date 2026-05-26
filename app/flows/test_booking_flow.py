from __future__ import annotations

import re
from datetime import timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.flows.base_flow import FlowMessage
from app.models import ConversationSession, Patient, TestBooking
from app.services.audit import write_audit
from app.services.cache import get_tests_cached, session_to_dict, update_session_cache
from app.templates.hinglish import (
    TEST_BOOKING_CANCELLED,
    TEST_BOOKING_CONFIRMED,
    TEST_BOOKING_UNKNOWN_CATEGORY,
    TEST_BOOKING_UNKNOWN_TEST,
    render_category_prompt,
    render_test_confirmation_prompt,
    render_test_selection_prompt,
)
from app.utils.datetime_utils import now_ist

TEST_BOOKING_FLOW = "test_booking"
SELECT_CATEGORY = "select_category"
SELECT_TEST = "select_test"
CONFIRM_BOOKING = "confirm_booking"
BOOKING_COMPLETE = "booking_complete"
YES_WORDS = {"haan", "ha", "yes", "confirm", "ok", "okay"}
NO_WORDS = {"nahi", "nahin", "no", "cancel"}


class TestBookingFlow:
    async def handle(
        self,
        session: ConversationSession | None,
        message: FlowMessage,
        db: AsyncSession,
    ) -> str:
        session = await ensure_booking_session(session, message, db)
        tests = await get_tests_cached(str(message.clinic_id), db)

        if session.step == SELECT_CATEGORY:
            return await handle_category_step(session, message, db, tests)
        if session.step == SELECT_TEST:
            return await handle_test_step(session, message, db, tests)
        if session.step == CONFIRM_BOOKING:
            return await handle_confirmation_step(session, message, db)

        session.step = SELECT_CATEGORY
        await persist_session(session, message, db)
        return render_category_prompt(categories_from_tests(tests))


async def ensure_booking_session(
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
            flow=TEST_BOOKING_FLOW,
            step=SELECT_CATEGORY,
            context={},
        )
        db.add(session)
    else:
        session.flow = TEST_BOOKING_FLOW
        session.step = session.step or SELECT_CATEGORY
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


async def handle_category_step(
    session: ConversationSession,
    message: FlowMessage,
    db: AsyncSession,
    tests: list[dict[str, object]],
) -> str:
    categories = categories_from_tests(tests)
    category = match_text(message.text, categories)
    if category is None:
        if not session.context:
            session.context = {"menu_prompted": True}
            await persist_session(session, message, db)
            return render_category_prompt(categories)
        await persist_session(session, message, db)
        return f"{TEST_BOOKING_UNKNOWN_CATEGORY}\n\n{render_category_prompt(categories)}"

    category_tests = [item for item in tests if item.get("category") == category]
    session.step = SELECT_TEST
    session.context = {
        "category": category,
        "available_test_ids": [str(item["id"]) for item in category_tests],
    }
    await persist_session(session, message, db)
    return render_test_selection_prompt(category, [str(item["name"]) for item in category_tests])


async def handle_test_step(
    session: ConversationSession,
    message: FlowMessage,
    db: AsyncSession,
    tests: list[dict[str, object]],
) -> str:
    available_ids = ids_from_context(session.context.get("available_test_ids"))
    available_tests = [item for item in tests if str(item.get("id")) in available_ids]
    selected = match_test(message.text, available_tests)
    if selected is None:
        await persist_session(session, message, db)
        category = str(session.context.get("category") or "")
        return (
            f"{TEST_BOOKING_UNKNOWN_TEST}\n\n"
            f"{render_test_selection_prompt(category, test_names(available_tests))}"
        )

    price = str(selected.get("price") or "0.00")
    session.step = CONFIRM_BOOKING
    session.context = {
        **session.context,
        "selected_test_id": str(selected["id"]),
        "selected_test_name": str(selected["name"]),
        "selected_test_price": price,
    }
    await persist_session(session, message, db)
    return render_test_confirmation_prompt(str(selected["name"]), price)


async def handle_confirmation_step(
    session: ConversationSession,
    message: FlowMessage,
    db: AsyncSession,
) -> str:
    decision = parse_confirmation(message.text)
    if decision is False:
        session.is_active = False
        session.step = BOOKING_COMPLETE
        await persist_session(session, message, db)
        return TEST_BOOKING_CANCELLED
    if decision is None:
        return render_test_confirmation_prompt(
            str(session.context["selected_test_name"]),
            str(session.context["selected_test_price"]),
        )

    booking = create_walkin_booking(session, message)
    db.add(booking)
    await db.flush()
    finish_session(session, booking)
    await db.commit()
    await write_booking_audit(db, message, booking)
    await update_session_cache(
        message.whatsapp_number,
        str(message.clinic_id),
        session_to_dict(session),
    )
    return TEST_BOOKING_CONFIRMED.format(test_name=booking.test_name)


def create_walkin_booking(session: ConversationSession, message: FlowMessage) -> TestBooking:
    return TestBooking(
        clinic_id=str(message.clinic_id),
        patient_id=str(session.patient_id),
        test_id=str(session.context["selected_test_id"]),
        test_name=str(session.context["selected_test_name"]),
        booking_type="walkin",
        status="booked",
        amount=Decimal(str(session.context["selected_test_price"])),
        payment_status="pending",
        payment_method="manual_offline",
    )


def finish_session(session: ConversationSession, booking: TestBooking) -> None:
    session.step = BOOKING_COMPLETE
    session.is_active = False
    session.context = {**session.context, "booking_id": str(booking.id)}


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
            "payment_status": booking.payment_status,
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


def categories_from_tests(tests: list[dict[str, object]]) -> list[str]:
    categories = {str(item["category"]) for item in tests if item.get("category")}
    return sorted(categories)


def match_text(message_text: str, choices: list[str]) -> str | None:
    normalized = normalize(message_text)
    for choice in choices:
        if normalize(choice) == normalized:
            return choice
    if normalized.isdigit():
        index = int(normalized) - 1
        if 0 <= index < len(choices):
            return choices[index]
    return None


def match_test(message_text: str, tests: list[dict[str, object]]) -> dict[str, object] | None:
    normalized = normalize(message_text)
    for item in tests:
        if normalize(str(item.get("name"))) == normalized:
            return item
    if normalized.isdigit():
        index = int(normalized) - 1
        if 0 <= index < len(tests):
            return tests[index]
    return None


def normalize(value: str) -> str:
    return " ".join(re.findall(r"[a-zA-Z0-9]+", value.lower()))


def ids_from_context(value: object) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {str(item) for item in value}


def parse_confirmation(message_text: str) -> bool | None:
    normalized = message_text.strip().lower()
    if normalized == "1":
        return True
    if normalized == "2":
        return False
    words = set(re.findall(r"[a-zA-Z]+", message_text.lower()))
    if words & NO_WORDS:
        return False
    if words & YES_WORDS:
        return True
    return None


def test_names(tests: list[dict[str, object]]) -> list[str]:
    return [str(item.get("name") or "") for item in tests]
