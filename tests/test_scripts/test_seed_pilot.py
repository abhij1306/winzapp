from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Clinic, Test
from scripts.register_meta_templates import build_template_payloads, register_templates
from scripts.seed_pilot import PILOT_FEATURE_FLAGS, PILOT_TEST_CATALOG, seed_pilot_data


@pytest.mark.asyncio
async def test_seed_pilot_creates_diagnostics_clinic_and_12_tests(
    db_session: AsyncSession,
) -> None:
    result = await seed_pilot_data(db_session)

    clinic = (await db_session.execute(select(Clinic))).scalar_one()
    tests = (await db_session.execute(select(Test).order_by(Test.sort_order))).scalars().all()

    assert result == {"clinic": "created", "tests_created": 12, "tests_updated": 0}
    assert clinic.name == "Pilot Diagnostics Clinic"
    assert clinic.clinic_type == "diagnostic"
    assert clinic.plan == "diagnostic"
    assert clinic.settings["features"] == PILOT_FEATURE_FLAGS
    assert len(tests) == 12
    assert [test.name for test in tests] == [item["name"] for item in PILOT_TEST_CATALOG]
    assert tests[0].price == Decimal("300.00")


@pytest.mark.asyncio
async def test_seed_pilot_is_idempotent(db_session: AsyncSession) -> None:
    await seed_pilot_data(db_session)
    result = await seed_pilot_data(db_session)

    clinic_count = (await db_session.execute(select(func.count()).select_from(Clinic))).scalar_one()
    test_count = (await db_session.execute(select(func.count()).select_from(Test))).scalar_one()

    assert result == {"clinic": "updated", "tests_created": 0, "tests_updated": 12}
    assert clinic_count == 1
    assert test_count == 12


def test_meta_template_payloads_cover_pilot_reminders() -> None:
    payloads = build_template_payloads()

    assert [payload["name"] for payload in payloads] == [
        "fasting_reminder",
        "report_ready",
        "recall_reminder",
        "review_request",
        "daily_digest",
    ]
    assert all(payload["language"] == "en_US" for payload in payloads)


@pytest.mark.asyncio
async def test_meta_template_registration_dry_run_does_not_call_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ExplodingClient:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            raise AssertionError("dry-run must not create an HTTP client")

    monkeypatch.setattr("scripts.register_meta_templates.httpx.AsyncClient", ExplodingClient)

    result = await register_templates(
        waba_id="waba-123",
        access_token="token",
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert result["template_count"] == 5
