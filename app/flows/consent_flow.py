from __future__ import annotations

import re
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.flows.base_flow import FlowMessage
from app.models import ConversationSession, Patient
from app.services.audit import write_audit
from app.services.cache import session_to_dict, update_session_cache
from app.templates.hinglish import (
    CONSENT_ACCEPTED,
    CONSENT_DECLINED,
    CONSENT_PROMPT,
    render_main_menu,
)
from app.utils.datetime_utils import now_ist

CONSENT_FLOW = "consent"
AWAITING_CONSENT = "awaiting_consent"
CONSENT_GRANTED = "consent_granted"
CONSENT_REFUSED = "consent_refused"
YES_WORDS = {"agree", "haan", "ha", "ok", "okay", "yes"}
NO_WORDS = {"nahi", "nahin", "no", "stop", "unsubscribe"}


class ConsentFlow:
    async def handle(
        self,
        session: ConversationSession | None,
        message: FlowMessage,
        db: AsyncSession,
    ) -> str:
        session = await ensure_consent_session(session, message, db)
        decision = parse_consent_decision(message.text)

        if decision is True:
            patient = await upsert_patient_consent(message, db, opt_in=True)
            await db.flush()
            finish_session(session, patient, CONSENT_GRANTED, automation_stopped=False)
            await commit_audit_and_cache(session, message, patient, db, "patient.opt_in")
            return f"{CONSENT_ACCEPTED}\n\n{render_main_menu()}"

        if decision is False:
            patient = await upsert_patient_consent(message, db, opt_in=False)
            await db.flush()
            finish_session(session, patient, CONSENT_REFUSED, automation_stopped=True)
            await commit_audit_and_cache(session, message, patient, db, "patient.opt_out")
            return CONSENT_DECLINED

        await touch_session(session, message, db)
        return CONSENT_PROMPT


async def ensure_consent_session(
    session: ConversationSession | None,
    message: FlowMessage,
    db: AsyncSession,
) -> ConversationSession:
    if session is None:
        session = ConversationSession(
            clinic_id=str(message.clinic_id),
            whatsapp_number=message.whatsapp_number,
            flow=CONSENT_FLOW,
            step=AWAITING_CONSENT,
            context={},
        )
        db.add(session)
    else:
        session.flow = CONSENT_FLOW
        session.step = session.step or AWAITING_CONSENT
        session.is_active = True

    await touch_session(session, message, db)
    return session


async def touch_session(
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


def parse_consent_decision(text: str) -> bool | None:
    normalized = text.strip().lower()
    if normalized == "1":
        return True
    if normalized == "2":
        return False
    words = set(re.findall(r"[a-zA-Z]+", text.lower()))
    if words & NO_WORDS:
        return False
    if words & YES_WORDS:
        return True
    return None


async def upsert_patient_consent(
    message: FlowMessage,
    db: AsyncSession,
    opt_in: bool,
) -> Patient:
    patient = await find_patient(message, db)
    if patient is None:
        patient = Patient(
            clinic_id=str(message.clinic_id),
            whatsapp_number=message.whatsapp_number,
            opt_in=opt_in,
        )
        db.add(patient)

    patient.opt_in = opt_in
    patient.opt_in_at = now_ist() if opt_in else None
    return patient


async def find_patient(message: FlowMessage, db: AsyncSession) -> Patient | None:
    statement = select(Patient).where(
        Patient.clinic_id == message.clinic_id,
        Patient.whatsapp_number == message.whatsapp_number,
        Patient.deleted_at.is_(None),
    )
    return (await db.execute(statement)).scalar_one_or_none()


def finish_session(
    session: ConversationSession,
    patient: Patient,
    step: str,
    automation_stopped: bool,
) -> None:
    session.patient_id = patient.id
    session.step = step
    session.is_active = False
    session.context = {**session.context, "automation_stopped": automation_stopped}


async def commit_audit_and_cache(
    session: ConversationSession,
    message: FlowMessage,
    patient: Patient,
    db: AsyncSession,
    action: str,
) -> None:
    await db.commit()
    await write_audit(
        db=db,
        clinic_id=message.clinic_id,
        actor_type="patient",
        action=action,
        entity_type="patient",
        entity_id=patient.id if isinstance(patient.id, UUID) else None,
        diff={"opt_in": patient.opt_in},
    )
    await update_session_cache(
        message.whatsapp_number,
        str(message.clinic_id),
        session_to_dict(session),
    )
