from __future__ import annotations

from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.api.errors import error_response
from app.api.v1.test_bookings import authorize_request
from app.config import get_settings
from app.database import get_db
from app.flows import FlowMessage
from app.models import FailedMessage
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.failed_message import FailedMessageData, FailedMessageResponse
from app.schemas.whatsapp_webhook import WAWebhookPayload
from app.services.audit import write_audit
from app.services.cache import get_clinic_cached
from app.services.flow_engine import handle_flow_message
from app.services.whatsapp_sender import send_text
from app.utils.datetime_utils import now_ist
from app.webhooks.whatsapp import (
    IncomingWhatsAppMessage,
    iter_incoming_messages,
    load_session_for_flow,
    log_inbound_message,
    message_already_processed,
    with_clinic_id,
)

router = APIRouter(prefix="/clinics/{clinic_id}/failed-messages", tags=["failed-messages"])


@router.get("", response_model=PaginatedResponse[FailedMessageData])
async def list_failed_messages(
    clinic_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    resolved: Annotated[bool, Query()] = False,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedResponse[FailedMessageData]:
    owner = await authorize_request(db, authorization, clinic_id)
    if isinstance(owner, JSONResponse):
        return cast(PaginatedResponse[FailedMessageData], owner)

    filters = failed_message_filters(clinic_id, resolved)
    total = await count_failed_messages(db, filters)
    statement = (
        select(FailedMessage)
        .where(*filters)
        .order_by(FailedMessage.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(statement)).scalars().all()
    return PaginatedResponse[FailedMessageData](
        data=[failed_message_data(row) for row in rows],
        pagination=PaginationMeta(page=page, page_size=page_size, total=total),
    )


@router.post("/{failed_message_id}/retry", response_model=FailedMessageResponse)
async def retry_failed_message(
    clinic_id: str,
    failed_message_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> FailedMessageResponse:
    owner = await authorize_request(db, authorization, clinic_id)
    if isinstance(owner, JSONResponse):
        return cast(FailedMessageResponse, owner)

    failed_message = await find_failed_message(db, clinic_id, failed_message_id)
    if failed_message is None:
        return failed_message_not_found()

    await mark_retry_started(db, failed_message)
    try:
        await replay_failed_payload(failed_message, db)
    except Exception as exc:
        await mark_retry_failed(db, failed_message, str(exc))
        return cast(
            FailedMessageResponse,
            error_response(
                502,
                "FAILED_MESSAGE_RETRY_FAILED",
                "Failed message replay did not complete.",
            ),
        )

    await mark_retry_resolved(db, failed_message)
    await write_retry_audit(db, failed_message)
    return FailedMessageResponse(data=failed_message_data(failed_message))


def failed_message_filters(
    clinic_id: str,
    resolved: bool,
) -> list[ColumnElement[bool]]:
    return [FailedMessage.clinic_id == clinic_id, FailedMessage.resolved.is_(resolved)]


async def count_failed_messages(db: AsyncSession, filters: list[ColumnElement[bool]]) -> int:
    statement = select(func.count()).select_from(FailedMessage).where(*filters)
    return int((await db.execute(statement)).scalar_one())


async def find_failed_message(
    db: AsyncSession,
    clinic_id: str,
    failed_message_id: str,
) -> FailedMessage | None:
    statement = select(FailedMessage).where(
        FailedMessage.clinic_id == clinic_id,
        FailedMessage.id == failed_message_id,
        FailedMessage.resolved.is_(False),
    )
    return (await db.execute(statement)).scalar_one_or_none()


def failed_message_not_found() -> FailedMessageResponse:
    return cast(
        FailedMessageResponse,
        error_response(404, "FAILED_MESSAGE_NOT_FOUND", "Failed message was not found."),
    )


async def mark_retry_started(db: AsyncSession, failed_message: FailedMessage) -> None:
    failed_message.retry_count += 1
    failed_message.last_retry_at = now_ist()
    await db.commit()


async def mark_retry_failed(
    db: AsyncSession,
    failed_message: FailedMessage,
    error: str,
) -> None:
    await db.rollback()
    failed_message.resolved = False
    failed_message.error = error
    failed_message.last_retry_at = now_ist()
    await db.commit()


async def mark_retry_resolved(db: AsyncSession, failed_message: FailedMessage) -> None:
    failed_message.resolved = True
    failed_message.error = None
    failed_message.last_retry_at = now_ist()
    await db.commit()


async def replay_failed_payload(
    failed_message: FailedMessage,
    db: AsyncSession,
) -> None:
    raw_payload = cast(dict[str, Any], failed_message.raw_payload)
    payload = WAWebhookPayload.model_validate(raw_payload)
    for item in iter_incoming_messages(payload, raw_payload):
        if should_replay_item(failed_message, item):
            await replay_incoming_item(item, raw_payload, db)
            return
    raise RuntimeError("Failed message payload did not contain the original message.")


def should_replay_item(
    failed_message: FailedMessage,
    item: IncomingWhatsAppMessage,
) -> bool:
    return (
        failed_message.wa_message_id is None
        or item.wa_message_id == failed_message.wa_message_id
    )


async def replay_incoming_item(
    item: IncomingWhatsAppMessage,
    _raw_payload: dict[str, Any],
    db: AsyncSession,
) -> None:
    clinic = await get_clinic_cached(item.phone_number_id, db)
    if clinic is None:
        raise RuntimeError("Clinic not found")

    item = with_clinic_id(item, str(clinic["id"]))
    if not await message_already_processed(db, item.wa_message_id, item.clinic_id):
        await log_inbound_message(db, item)

    session = await load_session_for_flow(db, item)
    response = await handle_flow_message(
        session,
        FlowMessage(
            clinic_id=item.clinic_id,
            whatsapp_number=item.whatsapp_number,
            text=item.text,
        ),
        clinic,
        db,
    )
    await send_text(
        item.phone_number_id,
        item.whatsapp_number,
        get_settings().wa_access_token,
        response,
    )


async def write_retry_audit(db: AsyncSession, failed_message: FailedMessage) -> None:
    await write_audit(
        db=db,
        clinic_id=failed_message.clinic_id,
        actor_type="owner",
        action="failed_message.retried",
        entity_type="failed_message",
        entity_id=failed_message.id if isinstance(failed_message.id, UUID) else None,
        diff={
            "retry_count": failed_message.retry_count,
            "resolved": failed_message.resolved,
        },
    )


def failed_message_data(failed_message: FailedMessage) -> FailedMessageData:
    return FailedMessageData(
        id=str(failed_message.id),
        clinic_id=str(failed_message.clinic_id) if failed_message.clinic_id else None,
        whatsapp_number=failed_message.whatsapp_number,
        wa_message_id=failed_message.wa_message_id,
        error=failed_message.error,
        retry_count=failed_message.retry_count,
        last_retry_at=failed_message.last_retry_at,
        resolved=failed_message.resolved,
        created_at=failed_message.created_at,
    )
