from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.flows.base_flow import FlowMessage
from app.flows.consent_flow import ConsentFlow
from app.models import AuditLog, Clinic, ConversationSession, Patient
from app.services.cache import get_session_cached
from app.templates.hinglish import (
    CONSENT_ACCEPTED,
    CONSENT_DECLINED,
    CONSENT_PROMPT,
    render_main_menu,
)


@pytest_asyncio.fixture
async def redis_client() -> Redis:
    client = Redis.from_url(get_settings().redis_url, decode_responses=True)
    await client.flushdb()
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()


async def create_clinic(db_session: AsyncSession, clinic_id: UUID) -> None:
    db_session.add(
        Clinic(
            id=clinic_id,
            name="Demo Diagnostics",
            whatsapp_number="+919000000001",
            owner_whatsapp="+919000000002",
            clinic_type="diagnostic",
            settings={},
        ),
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_first_patient_message_starts_consent_and_persists_session(
    db_session: AsyncSession,
    redis_client: Redis,
) -> None:
    clinic_id = uuid4()
    whatsapp_number = "+919999999999"
    await create_clinic(db_session, clinic_id)

    response = await ConsentFlow().handle(
        session=None,
        message=FlowMessage(
            clinic_id=clinic_id,
            whatsapp_number=whatsapp_number,
            text="Hi",
        ),
        db=db_session,
    )

    session = (
        await db_session.execute(
            select(ConversationSession).where(
                ConversationSession.clinic_id == clinic_id,
                ConversationSession.whatsapp_number == whatsapp_number,
            ),
        )
    ).scalar_one()
    cached = await get_session_cached(whatsapp_number, str(clinic_id), db_session)

    assert response == CONSENT_PROMPT
    assert session.flow == "consent"
    assert session.step == "awaiting_consent"
    assert session.is_active is True
    assert cached is not None
    assert cached["step"] == "awaiting_consent"


@pytest.mark.asyncio
async def test_consent_yes_updates_patient_and_audit_log(
    db_session: AsyncSession,
    redis_client: Redis,
) -> None:
    clinic_id = uuid4()
    whatsapp_number = "+919999999998"
    await create_clinic(db_session, clinic_id)
    session = ConversationSession(
        clinic_id=clinic_id,
        whatsapp_number=whatsapp_number,
        flow="consent",
        step="awaiting_consent",
        context={},
    )
    db_session.add(session)
    await db_session.commit()

    response = await ConsentFlow().handle(
        session=session,
        message=FlowMessage(
            clinic_id=clinic_id,
            whatsapp_number=whatsapp_number,
            text="Haan, I agree",
        ),
        db=db_session,
    )

    patient = (
        await db_session.execute(
            select(Patient).where(
                Patient.clinic_id == clinic_id,
                Patient.whatsapp_number == whatsapp_number,
                Patient.deleted_at.is_(None),
            ),
        )
    ).scalar_one()
    audit = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.clinic_id == clinic_id,
                AuditLog.action == "patient.opt_in",
            ),
        )
    ).scalar_one()
    cached = await get_session_cached(whatsapp_number, str(clinic_id), db_session)

    assert response == f"{CONSENT_ACCEPTED}\n\n{render_main_menu()}"
    assert patient.opt_in is True
    assert patient.opt_in_at is not None
    assert session.patient_id == patient.id
    assert session.step == "consent_granted"
    assert session.is_active is False
    assert audit.entity_id == patient.id
    assert cached is not None
    assert cached["is_active"] is False


@pytest.mark.asyncio
async def test_consent_no_updates_patient_and_stops_automation(
    db_session: AsyncSession,
    redis_client: Redis,
) -> None:
    clinic_id = uuid4()
    whatsapp_number = "+919999999997"
    await create_clinic(db_session, clinic_id)
    session = ConversationSession(
        clinic_id=clinic_id,
        whatsapp_number=whatsapp_number,
        flow="consent",
        step="awaiting_consent",
        context={},
    )
    db_session.add(session)
    await db_session.commit()

    response = await ConsentFlow().handle(
        session=session,
        message=FlowMessage(
            clinic_id=clinic_id,
            whatsapp_number=whatsapp_number,
            text="No, stop",
        ),
        db=db_session,
    )

    patient = (
        await db_session.execute(
            select(Patient).where(
                Patient.clinic_id == clinic_id,
                Patient.whatsapp_number == whatsapp_number,
                Patient.deleted_at.is_(None),
            ),
        )
    ).scalar_one()
    audit = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.clinic_id == clinic_id,
                AuditLog.action == "patient.opt_out",
            ),
        )
    ).scalar_one()
    cached = await get_session_cached(whatsapp_number, str(clinic_id), db_session)

    assert response == CONSENT_DECLINED
    assert patient.opt_in is False
    assert session.patient_id == patient.id
    assert session.step == "consent_refused"
    assert session.is_active is False
    assert session.context["automation_stopped"] is True
    assert audit.entity_id == patient.id
    assert cached is not None
    assert cached["step"] == "consent_refused"


@pytest.mark.asyncio
async def test_unclear_consent_answer_reprompts_without_patient_change(
    db_session: AsyncSession,
    redis_client: Redis,
) -> None:
    clinic_id = uuid4()
    whatsapp_number = "+919999999996"
    await create_clinic(db_session, clinic_id)
    session = ConversationSession(
        clinic_id=clinic_id,
        whatsapp_number=whatsapp_number,
        flow="consent",
        step="awaiting_consent",
        context={},
    )
    db_session.add(session)
    await db_session.commit()

    response = await ConsentFlow().handle(
        session=session,
        message=FlowMessage(
            clinic_id=clinic_id,
            whatsapp_number=whatsapp_number,
            text="Maybe later",
        ),
        db=db_session,
    )

    patients = (
        await db_session.execute(
            select(Patient).where(
                Patient.clinic_id == clinic_id,
                Patient.whatsapp_number == whatsapp_number,
            ),
        )
    ).scalars().all()

    assert response == CONSENT_PROMPT
    assert patients == []
    assert session.step == "awaiting_consent"
    assert session.is_active is True
