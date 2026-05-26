from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.flows import (
    AdminFlow,
    BaseFlow,
    CancellationFlow,
    ConsentFlow,
    FlowMessage,
    HomeCollectionFlow,
    ReportInquiryFlow,
    TestBookingFlow,
)
from app.models import ConversationSession, Patient
from app.services.cache import session_to_dict, update_session_cache
from app.services.intent_router import DiagnosticIntent, classify_diagnostics_intent
from app.templates.hinglish import PATIENT_UNKNOWN_INTENT, render_main_menu
from app.utils.datetime_utils import now_ist


async def handle_flow_message(
    session: ConversationSession | None,
    message: FlowMessage,
    clinic: dict[str, object],
    db: AsyncSession,
) -> str:
    menu_response = await maybe_handle_patient_menu(session, message, clinic, db)
    if menu_response is not None:
        return menu_response
    flow = await resolve_flow(session, message, clinic, db)
    if flow is None:
        return PATIENT_UNKNOWN_INTENT
    return await flow.handle(session, message, db)


async def maybe_handle_patient_menu(
    session: ConversationSession | None,
    message: FlowMessage,
    clinic: dict[str, object],
    db: AsyncSession,
) -> str | None:
    if clinic.get("owner_whatsapp") == message.whatsapp_number:
        return None

    patient = await find_patient(message, db)
    if patient is None or not patient.opt_in or patient.opt_in_at is None:
        return None

    if is_main_menu_request(message.text):
        await reset_active_session(session, message, db)
        return render_main_menu()

    if continued_flow(session) is not None:
        return None

    menu_choice = main_menu_choice(message.text)
    if menu_choice is None:
        return None

    flow = named_flow(menu_choice)
    if flow is None:
        return render_main_menu()
    return await flow.handle(
        None,
        FlowMessage(
            clinic_id=message.clinic_id,
            whatsapp_number=message.whatsapp_number,
            text="",
        ),
        db,
    )


async def resolve_flow(
    session: ConversationSession | None,
    message: FlowMessage,
    clinic: dict[str, object],
    db: AsyncSession,
) -> BaseFlow | None:
    if clinic.get("owner_whatsapp") == message.whatsapp_number:
        return AdminFlow()

    patient = await find_patient(message, db)
    if patient is None or not patient.opt_in or patient.opt_in_at is None:
        return ConsentFlow()

    active_flow = continued_flow(session)
    if active_flow is not None:
        return active_flow

    intent = await classify_diagnostics_intent(message.text, str(message.clinic_id), db)
    return intent_flow(intent.intent)


async def find_patient(message: FlowMessage, db: AsyncSession) -> Patient | None:
    statement = select(Patient).where(
        Patient.clinic_id == message.clinic_id,
        Patient.whatsapp_number == message.whatsapp_number,
        Patient.deleted_at.is_(None),
    )
    return (await db.execute(statement)).scalar_one_or_none()


def continued_flow(session: ConversationSession | None) -> BaseFlow | None:
    if session is None or not session.is_active:
        return None
    return named_flow(session.flow)


def intent_flow(intent: DiagnosticIntent) -> BaseFlow | None:
    return named_flow(intent)


def named_flow(flow_name: str | None) -> BaseFlow | None:
    if flow_name == "test_booking":
        return TestBookingFlow()
    if flow_name == "home_collection":
        return HomeCollectionFlow()
    if flow_name == "report_inquiry":
        return ReportInquiryFlow()
    if flow_name == "cancel":
        return CancellationFlow()
    if flow_name == "admin":
        return AdminFlow()
    return None


def is_main_menu_request(text: str) -> bool:
    normalized = " ".join(text.lower().split())
    return normalized in {"0", "menu", "main menu", "mainmenu", "start", "home"}


def main_menu_choice(text: str) -> DiagnosticIntent | None:
    normalized = text.strip()
    if normalized == "1":
        return "test_booking"
    if normalized == "2":
        return "home_collection"
    if normalized == "3":
        return "report_inquiry"
    if normalized == "4":
        return "cancel"
    return None


async def reset_active_session(
    session: ConversationSession | None,
    message: FlowMessage,
    db: AsyncSession,
) -> None:
    if session is None or not session.is_active:
        return

    session.is_active = False
    session.last_message_at = now_ist()
    await db.commit()
    await update_session_cache(
        message.whatsapp_number,
        str(message.clinic_id),
        session_to_dict(session),
    )
