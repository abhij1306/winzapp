from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth_context import CurrentOwner, authenticate_owner
from app.api.errors import error_response
from app.database import get_db
from app.models import Clinic
from app.schemas.clinic_settings import (
    ClinicSettingsData,
    ClinicSettingsResponse,
    ClinicSettingsUpdateRequest,
)
from app.services.audit import write_audit
from app.services.cache import invalidate_clinic_cache, invalidate_clinic_id_cache

router = APIRouter(prefix="/clinics", tags=["clinics"])


@router.get("/{clinic_id}", response_model=ClinicSettingsResponse)
async def get_clinic_settings(
    clinic_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> ClinicSettingsResponse:
    owner = authenticate_owner(authorization, clinic_id)
    if isinstance(owner, JSONResponse):
        return cast(ClinicSettingsResponse, owner)

    clinic = await find_authorized_clinic(db, clinic_id, owner)
    if clinic is None:
        return cast(
            ClinicSettingsResponse,
            error_response(404, "CLINIC_NOT_FOUND", "Clinic was not found."),
        )
    return ClinicSettingsResponse(data=clinic_settings_data(clinic))


@router.put("/{clinic_id}", response_model=ClinicSettingsResponse)
async def update_clinic_settings(
    clinic_id: str,
    payload: ClinicSettingsUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> ClinicSettingsResponse:
    owner = authenticate_owner(authorization, clinic_id)
    if isinstance(owner, JSONResponse):
        return cast(ClinicSettingsResponse, owner)

    clinic = await find_authorized_clinic(db, clinic_id, owner)
    if clinic is None:
        return cast(
            ClinicSettingsResponse,
            error_response(404, "CLINIC_NOT_FOUND", "Clinic was not found."),
        )

    before = clinic_snapshot(clinic)
    old_phone_number_id = phone_number_id(clinic.settings)
    apply_update(clinic, payload)
    await db.commit()
    await invalidate_clinic_caches(
        str(clinic.id),
        old_phone_number_id,
        phone_number_id(clinic.settings),
    )
    await write_clinic_update_audit(db, clinic, before)
    return ClinicSettingsResponse(data=clinic_settings_data(clinic))


async def find_authorized_clinic(
    db: AsyncSession,
    clinic_id: str,
    owner: CurrentOwner,
) -> Clinic | None:
    statement = select(Clinic).where(
        Clinic.id == clinic_id,
        Clinic.owner_whatsapp == owner.owner_whatsapp,
        Clinic.deleted_at.is_(None),
    )
    return (await db.execute(statement)).scalar_one_or_none()


def apply_update(clinic: Clinic, payload: ClinicSettingsUpdateRequest) -> None:
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(clinic, field, value)


async def invalidate_clinic_caches(
    clinic_id: str,
    old_phone_number_id: str | None,
    new_phone_number_id: str | None,
) -> None:
    await invalidate_clinic_id_cache(clinic_id)
    if old_phone_number_id:
        await invalidate_clinic_cache(old_phone_number_id)
    if new_phone_number_id and new_phone_number_id != old_phone_number_id:
        await invalidate_clinic_cache(new_phone_number_id)


async def write_clinic_update_audit(
    db: AsyncSession,
    clinic: Clinic,
    before: dict[str, object],
) -> None:
    await write_audit(
        db=db,
        clinic_id=clinic.id,
        actor_type="owner",
        action="clinic.updated",
        entity_type="clinic",
        entity_id=clinic.id if isinstance(clinic.id, UUID) else None,
        diff={"before": before, "after": clinic_snapshot(clinic)},
    )


def clinic_settings_data(clinic: Clinic) -> ClinicSettingsData:
    return ClinicSettingsData(**clinic_snapshot(clinic))


def clinic_snapshot(clinic: Clinic) -> dict[str, object]:
    return {
        "id": str(clinic.id),
        "name": clinic.name,
        "owner_name": clinic.owner_name,
        "clinic_type": clinic.clinic_type,
        "whatsapp_number": clinic.whatsapp_number,
        "owner_whatsapp": clinic.owner_whatsapp,
        "address": clinic.address,
        "city": clinic.city,
        "pincode": clinic.pincode,
        "timezone": clinic.timezone,
        "plan": clinic.plan,
        "plan_active": clinic.plan_active,
        "settings": clinic.settings,
    }


def phone_number_id(settings: dict[str, object]) -> str | None:
    value = settings.get("wa_phone_number_id")
    return str(value) if value else None
