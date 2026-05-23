from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.auth as auth_service
import app.services.whatsapp_sender as whatsapp_sender
from app.api.errors import error_response
from app.config import get_settings
from app.database import get_db
from app.models import Clinic
from app.schemas.auth import (
    OtpSendData,
    OtpSendRequest,
    OtpSendResponse,
    OtpVerifyData,
    OtpVerifyRequest,
    OtpVerifyResponse,
)
from app.templates.hinglish import OTP_LOGIN_MESSAGE

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/otp/send", response_model=OtpSendResponse)
async def send_otp(
    payload: OtpSendRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OtpSendResponse:
    clinic = await find_owner_clinic(db, payload.owner_whatsapp)
    if clinic is None:
        return cast(
            OtpSendResponse,
            error_response(404, "OWNER_NOT_FOUND", "Owner WhatsApp number was not found."),
        )

    otp = auth_service.generate_otp()
    await auth_service.store_otp(payload.owner_whatsapp, str(clinic.id), otp)
    await whatsapp_sender.send_text(
        phone_number_id=clinic_phone_number_id(clinic),
        to=payload.owner_whatsapp,
        access_token=get_settings().wa_access_token,
        body=OTP_LOGIN_MESSAGE.format(otp=otp),
    )
    return OtpSendResponse(data=OtpSendData(status="otp_sent"))


@router.post("/otp/verify", response_model=OtpVerifyResponse)
async def verify_otp(
    payload: OtpVerifyRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OtpVerifyResponse:
    clinic_id = await auth_service.verify_stored_otp(payload.owner_whatsapp, payload.otp)
    if clinic_id is None:
        return cast(
            OtpVerifyResponse,
            error_response(401, "INVALID_OTP", "OTP is invalid or expired."),
        )

    clinic = await find_owner_clinic(db, payload.owner_whatsapp)
    if clinic is None or str(clinic.id) != clinic_id:
        return cast(
            OtpVerifyResponse,
            error_response(401, "INVALID_OTP", "OTP is invalid or expired."),
        )

    settings = get_settings()
    return OtpVerifyResponse(
        data=OtpVerifyData(
            access_token=auth_service.create_access_token(payload.owner_whatsapp, clinic_id),
            token_type="bearer",
            expires_in=settings.jwt_access_token_minutes * 60,
        ),
    )


async def find_owner_clinic(db: AsyncSession, owner_whatsapp: str) -> Clinic | None:
    statement = select(Clinic).where(
        Clinic.owner_whatsapp == owner_whatsapp,
        Clinic.deleted_at.is_(None),
    )
    return (await db.execute(statement)).scalar_one_or_none()


def clinic_phone_number_id(clinic: Clinic) -> str:
    value = clinic.settings.get("wa_phone_number_id")
    return str(value or "")
