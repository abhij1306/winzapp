from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.flows import ConsentFlow, FlowMessage
from app.models import ConversationSession, FailedMessage, Message
from app.schemas.whatsapp_webhook import WAMessage, WAWebhookPayload
from app.services.cache import get_clinic_cached, get_session_cached
from app.services.whatsapp_sender import send_text

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


@dataclass(frozen=True)
class IncomingWhatsAppMessage:
    phone_number_id: str
    clinic_id: str
    wa_message_id: str
    whatsapp_number: str
    message_type: str
    text: str
    raw_message: dict[str, object]


@router.get("/whatsapp", response_class=PlainTextResponse)
async def verify_webhook(
    mode: str | None = Query(default=None, alias="hub.mode"),
    verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    challenge: str = Query(default="", alias="hub.challenge"),
) -> str:
    settings = get_settings()
    if mode == "subscribe" and verify_token == settings.wa_verify_token:
        return challenge
    raise HTTPException(status_code=403, detail="Invalid verify token")


@router.post("/whatsapp")
async def receive_whatsapp_webhook(
    request: Request,
    db: DbSession,
) -> dict[str, str]:
    raw_body = await request.body()
    verify_signature(raw_body, request.headers.get("x-hub-signature-256"))
    raw_payload = json.loads(raw_body)
    payload = WAWebhookPayload.model_validate(raw_payload)

    for item in iter_incoming_messages(payload, raw_payload):
        await process_incoming_message(item, raw_payload, db)

    return {"status": "ok"}


def verify_signature(raw_body: bytes, signature: str | None) -> None:
    secret = get_settings().wa_app_secret
    expected = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    if not signature or not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=403, detail="Invalid WhatsApp signature")


def iter_incoming_messages(
    payload: WAWebhookPayload,
    raw_payload: dict[str, Any],
) -> list[IncomingWhatsAppMessage]:
    result: list[IncomingWhatsAppMessage] = []
    for entry in payload.entry:
        for change in entry.changes:
            metadata = change.value.metadata
            if metadata is None:
                continue
            for message in change.value.messages:
                result.append(
                    build_incoming_message(metadata.phone_number_id, message, raw_payload),
                )
    return result


def build_incoming_message(
    phone_number_id: str,
    message: WAMessage,
    _raw_payload: dict[str, Any],
) -> IncomingWhatsAppMessage:
    return IncomingWhatsAppMessage(
        phone_number_id=phone_number_id,
        clinic_id="",
        wa_message_id=message.id,
        whatsapp_number=message.from_,
        message_type=message.type,
        text=extract_message_text(message),
        raw_message=message.model_dump(by_alias=True, exclude_none=True),
    )


def extract_message_text(message: WAMessage) -> str:
    if message.text is not None:
        return message.text.body
    if message.button is not None:
        return str(message.button.get("text", ""))
    if message.interactive is not None:
        return str(message.interactive)
    return message.type


async def process_incoming_message(
    item: IncomingWhatsAppMessage,
    raw_payload: dict[str, Any],
    db: AsyncSession,
) -> None:
    if await message_already_processed(db, item.wa_message_id):
        return

    clinic = await get_clinic_cached(item.phone_number_id, db)
    if clinic is None:
        await write_failed_message(db, None, item, raw_payload, "Clinic not found")
        return

    item = with_clinic_id(item, str(clinic["id"]))
    await log_inbound_message(db, item)

    try:
        session = await load_session_for_flow(db, item)
        response = await ConsentFlow().handle(
            session,
            FlowMessage(
                clinic_id=item.clinic_id,
                whatsapp_number=item.whatsapp_number,
                text=item.text,
            ),
            db,
        )
        await send_text(
            item.phone_number_id,
            item.whatsapp_number,
            get_settings().wa_access_token,
            response,
        )
    except Exception as exc:
        await write_failed_message(db, item.clinic_id, item, raw_payload, str(exc))


def with_clinic_id(item: IncomingWhatsAppMessage, clinic_id: str) -> IncomingWhatsAppMessage:
    return IncomingWhatsAppMessage(
        phone_number_id=item.phone_number_id,
        clinic_id=clinic_id,
        wa_message_id=item.wa_message_id,
        whatsapp_number=item.whatsapp_number,
        message_type=item.message_type,
        text=item.text,
        raw_message=item.raw_message,
    )


async def message_already_processed(db: AsyncSession, wa_message_id: str) -> bool:
    statement = select(Message.id).where(Message.wa_message_id == wa_message_id)
    return (await db.execute(statement)).scalar_one_or_none() is not None


async def log_inbound_message(db: AsyncSession, item: IncomingWhatsAppMessage) -> None:
    db.add(
        Message(
            clinic_id=item.clinic_id,
            whatsapp_number=item.whatsapp_number,
            direction="inbound",
            message_type=item.message_type,
            content=item.text,
            metadata_json=item.raw_message,
            wa_message_id=item.wa_message_id,
        ),
    )
    await db.commit()


async def load_session_for_flow(
    db: AsyncSession,
    item: IncomingWhatsAppMessage,
) -> ConversationSession | None:
    cached = await get_session_cached(item.whatsapp_number, item.clinic_id, db)
    if cached is None:
        return None

    statement = select(ConversationSession).where(
        ConversationSession.clinic_id == item.clinic_id,
        ConversationSession.whatsapp_number == item.whatsapp_number,
        ConversationSession.is_active.is_(True),
    )
    return (await db.execute(statement)).scalar_one_or_none()


async def write_failed_message(
    db: AsyncSession,
    clinic_id: str | None,
    item: IncomingWhatsAppMessage,
    raw_payload: dict[str, Any],
    error: str,
) -> None:
    await rollback_quietly(db)
    db.add(
        FailedMessage(
            clinic_id=clinic_id,
            whatsapp_number=item.whatsapp_number,
            wa_message_id=item.wa_message_id,
            raw_payload=raw_payload,
            error=error,
        ),
    )
    await db.commit()


async def rollback_quietly(db: AsyncSession) -> None:
    try:
        await db.rollback()
    except Exception:
        return
