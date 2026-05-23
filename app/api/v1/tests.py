from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.api.errors import error_response
from app.api.v1.test_bookings import authorize_request
from app.database import get_db
from app.models import Test
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.test_catalog import (
    TestCatalogCreateRequest,
    TestCatalogData,
    TestCatalogResponse,
    TestCatalogUpdateRequest,
)
from app.services.audit import write_audit
from app.services.cache import invalidate_tests_cache
from app.utils.datetime_utils import now_ist

router = APIRouter(prefix="/clinics/{clinic_id}/tests", tags=["tests"])


@router.get("", response_model=PaginatedResponse[TestCatalogData])
async def list_tests(
    clinic_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    active: Annotated[bool | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedResponse[TestCatalogData]:
    owner = await authorize_request(db, authorization, clinic_id)
    if isinstance(owner, JSONResponse):
        return cast(PaginatedResponse[TestCatalogData], owner)

    filters = test_filters(clinic_id, active)
    total = await count_tests(db, filters)
    statement = (
        select(Test)
        .where(*filters)
        .order_by(Test.sort_order, Test.name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    tests = (await db.execute(statement)).scalars().all()
    return PaginatedResponse[TestCatalogData](
        data=[test_data(test) for test in tests],
        pagination=PaginationMeta(page=page, page_size=page_size, total=total),
    )


@router.post("", response_model=TestCatalogResponse, status_code=201)
async def create_test(
    clinic_id: str,
    payload: TestCatalogCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> TestCatalogResponse:
    owner = await authorize_request(db, authorization, clinic_id)
    if isinstance(owner, JSONResponse):
        return cast(TestCatalogResponse, owner)

    test = Test(clinic_id=clinic_id, **payload.model_dump())
    db.add(test)
    await db.commit()
    await invalidate_tests_cache(clinic_id)
    await write_test_audit(db, test, "test.created", None)
    return TestCatalogResponse(data=test_data(test))


@router.put("/{test_id}", response_model=TestCatalogResponse)
async def update_test(
    clinic_id: str,
    test_id: str,
    payload: TestCatalogUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> TestCatalogResponse:
    owner = await authorize_request(db, authorization, clinic_id)
    if isinstance(owner, JSONResponse):
        return cast(TestCatalogResponse, owner)

    test = await find_test(db, clinic_id, test_id)
    if test is None:
        return test_not_found()

    before = test_snapshot(test)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(test, field, value)
    await db.commit()
    await invalidate_tests_cache(clinic_id)
    await write_test_audit(db, test, "test.updated", before)
    return TestCatalogResponse(data=test_data(test))


@router.delete("/{test_id}", response_model=TestCatalogResponse)
async def delete_test(
    clinic_id: str,
    test_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> TestCatalogResponse:
    owner = await authorize_request(db, authorization, clinic_id)
    if isinstance(owner, JSONResponse):
        return cast(TestCatalogResponse, owner)

    test = await find_test(db, clinic_id, test_id)
    if test is None:
        return test_not_found()

    before = test_snapshot(test)
    test.is_active = False
    test.deleted_at = now_ist()
    test.deleted_by = None
    await db.commit()
    await invalidate_tests_cache(clinic_id)
    await write_test_audit(db, test, "test.deleted", before)
    return TestCatalogResponse(data=test_data(test))


def test_filters(clinic_id: str, active: bool | None) -> list[ColumnElement[bool]]:
    filters: list[ColumnElement[bool]] = [Test.clinic_id == clinic_id, Test.deleted_at.is_(None)]
    if active is not None:
        filters.append(Test.is_active.is_(active))
    return filters


async def count_tests(db: AsyncSession, filters: list[ColumnElement[bool]]) -> int:
    statement = select(func.count()).select_from(Test).where(*filters)
    return int((await db.execute(statement)).scalar_one())


async def find_test(db: AsyncSession, clinic_id: str, test_id: str) -> Test | None:
    statement = select(Test).where(
        Test.clinic_id == clinic_id,
        Test.id == test_id,
        Test.deleted_at.is_(None),
    )
    return (await db.execute(statement)).scalar_one_or_none()


def test_not_found() -> TestCatalogResponse:
    return cast(
        TestCatalogResponse,
        error_response(404, "TEST_NOT_FOUND", "Test was not found."),
    )


async def write_test_audit(
    db: AsyncSession,
    test: Test,
    action: str,
    before: dict[str, object] | None,
) -> None:
    await write_audit(
        db=db,
        clinic_id=test.clinic_id,
        actor_type="owner",
        action=action,
        entity_type="test",
        entity_id=test.id if isinstance(test.id, UUID) else None,
        diff={"before": before, "after": test_snapshot(test)},
    )


def test_data(test: Test) -> TestCatalogData:
    return TestCatalogData(**test_snapshot(test))


def test_snapshot(test: Test) -> dict[str, object]:
    return {
        "id": str(test.id),
        "name": test.name,
        "name_hindi": test.name_hindi,
        "description": test.description,
        "price": str(test.price) if test.price is not None else None,
        "duration_hours": test.duration_hours,
        "requires_fasting": test.requires_fasting,
        "home_collection_available": test.home_collection_available,
        "category": test.category,
        "is_active": test.is_active,
        "sort_order": test.sort_order,
    }
