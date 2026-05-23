from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.services.feature_flags import require_feature


@pytest.mark.asyncio
async def test_enabled_feature_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    async def cached_clinic(_clinic_id: str, _db: object) -> dict[str, object]:
        return {"settings": {"features": {"broadcasts": True}}}

    monkeypatch.setattr("app.services.feature_flags.get_clinic_by_id_cached", cached_clinic)

    await require_feature(str(uuid4()), "broadcasts", object())


@pytest.mark.asyncio
async def test_disabled_feature_raises_403(monkeypatch: pytest.MonkeyPatch) -> None:
    async def cached_clinic(_clinic_id: str, _db: object) -> dict[str, object]:
        return {"settings": {"features": {"broadcasts": False}}}

    monkeypatch.setattr("app.services.feature_flags.get_clinic_by_id_cached", cached_clinic)

    with pytest.raises(HTTPException) as exc_info:
        await require_feature(str(uuid4()), "broadcasts", object())

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["error"]["code"] == "PLAN_FEATURE_DISABLED"


@pytest.mark.asyncio
async def test_missing_feature_flag_raises_403(monkeypatch: pytest.MonkeyPatch) -> None:
    async def cached_clinic(_clinic_id: str, _db: object) -> dict[str, object]:
        return {"settings": {"features": {}}}

    monkeypatch.setattr("app.services.feature_flags.get_clinic_by_id_cached", cached_clinic)

    with pytest.raises(HTTPException) as exc_info:
        await require_feature(str(uuid4()), "broadcasts", object())

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_missing_clinic_raises_403(monkeypatch: pytest.MonkeyPatch) -> None:
    async def cached_clinic(_clinic_id: str, _db: object) -> None:
        return None

    monkeypatch.setattr("app.services.feature_flags.get_clinic_by_id_cached", cached_clinic)

    with pytest.raises(HTTPException) as exc_info:
        await require_feature(str(uuid4()), "broadcasts", object())

    assert exc_info.value.status_code == 403
