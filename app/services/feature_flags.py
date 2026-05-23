from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.common import ErrorDetail, ErrorEnvelope
from app.services.cache import get_clinic_by_id_cached


async def require_feature(clinic_id: str, feature_name: str, db: AsyncSession) -> None:
    clinic = await get_clinic_by_id_cached(clinic_id, db)
    features = get_features(clinic)

    if features.get(feature_name) is True:
        return

    envelope = ErrorEnvelope(
        error=ErrorDetail(
            code="PLAN_FEATURE_DISABLED",
            message=f"Feature '{feature_name}' is not enabled for this clinic.",
            details={"feature": feature_name},
            request_id="unavailable",
        ),
    )
    raise HTTPException(status_code=403, detail=envelope.model_dump())


def get_features(clinic: dict[str, object] | None) -> dict[str, bool]:
    if clinic is None:
        return {}

    settings = clinic.get("settings")
    if not isinstance(settings, dict):
        return {}

    features = settings.get("features")
    if not isinstance(features, dict):
        return {}

    return {
        key: value
        for key, value in features.items()
        if isinstance(key, str) and isinstance(value, bool)
    }
