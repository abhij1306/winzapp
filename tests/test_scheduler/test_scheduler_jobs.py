from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app import main as main_app
from app.config import get_settings
from app.models import Clinic, Patient, RecallSchedule, Test, TestBooking
from app.services.cache import redis_get
from app.services.scheduler import (
    HEARTBEAT_KEY,
    check_scheduler_heartbeat_freshness,
    create_scheduler,
    send_daily_digests,
    send_fasting_reminders,
    send_recall_reminders,
    send_review_requests,
    write_scheduler_heartbeat,
)
from app.utils.datetime_utils import now_ist


@pytest_asyncio.fixture
async def redis_client() -> AsyncGenerator[Redis, None]:
    client = Redis.from_url(get_settings().redis_url, decode_responses=True)
    await client.flushdb()
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()


async def create_scheduler_fixture(
    db_session: AsyncSession,
    suffix: str = "6001",
) -> tuple[Clinic, Patient, TestBooking]:
    clinic = Clinic(
        id=uuid4(),
        name="Scheduler Diagnostics",
        owner_name="Owner",
        whatsapp_number=f"+91810000{suffix}",
        owner_whatsapp=f"+91900000{suffix}",
        clinic_type="diagnostic",
        gbp_review_link="https://maps.example/review",
        settings={"wa_phone_number_id": f"phone-scheduler-{suffix}"},
    )
    patient = Patient(
        clinic_id=clinic.id,
        whatsapp_number=f"+91770000{suffix}",
        name="Anita",
        opt_in=True,
    )
    test = Test(
        clinic_id=clinic.id,
        name="HbA1c",
        price=Decimal("450.00"),
        requires_fasting=True,
        category="Diabetes",
    )
    booking = TestBooking(
        clinic_id=clinic.id,
        patient=patient,
        test=test,
        test_name="HbA1c",
        booking_type="home_collection",
        status="booked",
        collection_slot=now_ist() + timedelta(hours=12),
        amount=Decimal("450.00"),
        payment_status="paid",
    )
    db_session.add_all([clinic, patient, test, booking])
    await db_session.commit()
    return clinic, patient, booking


@pytest.mark.asyncio
async def test_send_fasting_reminders_sends_due_template_once(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clinic, patient, booking = await create_scheduler_fixture(db_session)
    await create_scheduler_fixture(db_session, "6002")
    sent: list[dict[str, object]] = []

    async def fake_send_template(
        phone_number_id: str,
        to: str,
        access_token: str,
        template_name: str,
        language_code: str,
        components: list[dict[str, object]] | None = None,
    ) -> dict[str, object]:
        sent.append({"to": to, "template_name": template_name, "components": components})
        return {"messages": [{"id": "wamid.fasting"}]}

    monkeypatch.setattr("app.services.whatsapp_sender.send_template", fake_send_template)

    count = await send_fasting_reminders(db_session, str(clinic.id))

    assert count == 1
    assert sent[0]["to"] == patient.whatsapp_number
    assert sent[0]["template_name"] == "fasting_reminder"
    assert booking.fasting_reminder_sent is True
    assert str(clinic.id) in str(sent[0]["components"])


@pytest.mark.asyncio
async def test_send_recall_reminders_marks_due_recalls_sent(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clinic, patient, booking = await create_scheduler_fixture(db_session)
    recall = RecallSchedule(
        clinic_id=clinic.id,
        patient_id=patient.id,
        trigger_type="hba1c_quarterly",
        trigger_at=now_ist() - timedelta(minutes=5),
        message_template="recall_reminder",
        reference_id=booking.id,
    )
    db_session.add(recall)
    await db_session.commit()
    sent: list[str] = []

    async def fake_send_template(
        phone_number_id: str,
        to: str,
        access_token: str,
        template_name: str,
        language_code: str,
        components: list[dict[str, object]] | None = None,
    ) -> dict[str, object]:
        sent.append(template_name)
        return {"messages": [{"id": "wamid.recall"}]}

    monkeypatch.setattr("app.services.whatsapp_sender.send_template", fake_send_template)

    count = await send_recall_reminders(db_session, str(clinic.id))

    assert count == 1
    assert sent == ["recall_reminder"]
    assert recall.status == "sent"
    assert recall.sent_at is not None


@pytest.mark.asyncio
async def test_send_review_requests_marks_booking_notes(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clinic, patient, booking = await create_scheduler_fixture(db_session)
    booking.status = "delivered"
    booking.report_delivered_at = now_ist() - timedelta(minutes=10)
    await db_session.commit()
    sent: list[str] = []

    async def fake_send_template(
        phone_number_id: str,
        to: str,
        access_token: str,
        template_name: str,
        language_code: str,
        components: list[dict[str, object]] | None = None,
    ) -> dict[str, object]:
        sent.append(to)
        return {"messages": [{"id": "wamid.review"}]}

    monkeypatch.setattr("app.services.whatsapp_sender.send_template", fake_send_template)

    count = await send_review_requests(db_session, str(booking.clinic_id))

    assert count == 1
    assert sent == [patient.whatsapp_number]
    assert "review_request_sent=true" in str(booking.notes)


@pytest.mark.asyncio
async def test_send_daily_digests_sends_owner_stats(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clinic, _patient, booking = await create_scheduler_fixture(db_session)
    booking.status = "delivered"
    booking.report_delivered_at = now_ist()
    await db_session.commit()
    sent: list[dict[str, object]] = []

    async def fake_send_template(
        phone_number_id: str,
        to: str,
        access_token: str,
        template_name: str,
        language_code: str,
        components: list[dict[str, object]] | None = None,
    ) -> dict[str, object]:
        sent.append({"to": to, "template_name": template_name, "components": components})
        return {"messages": [{"id": "wamid.digest"}]}

    monkeypatch.setattr("app.services.whatsapp_sender.send_template", fake_send_template)

    count = await send_daily_digests(db_session, str(clinic.id))

    assert count == 1
    assert sent[0]["to"] == clinic.owner_whatsapp
    assert sent[0]["template_name"] == "daily_digest"
    assert "Reports delivered today" in str(sent[0]["components"])


@pytest.mark.asyncio
async def test_scheduler_heartbeat_and_registration(redis_client: Redis) -> None:
    await write_scheduler_heartbeat()
    scheduler = create_scheduler()

    assert await redis_get("scheduler:heartbeat") is not None
    assert str(scheduler.timezone) == "Asia/Kolkata"
    assert {job.id for job in scheduler.get_jobs()} == {
        "fasting-reminders",
        "review-requests",
        "recall-reminders",
        "daily-digest",
        "scheduler-heartbeat",
        "scheduler-heartbeat-alert",
    }


@pytest.mark.asyncio
async def test_scheduler_heartbeat_alerts_when_missing(
    redis_client: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    alerts: list[tuple[str, str]] = []

    def fake_alert(alert_type: str, message: str, **_fields: object) -> None:
        alerts.append((alert_type, message))

    monkeypatch.setattr("app.services.scheduler.emit_alert", fake_alert)

    is_fresh = await check_scheduler_heartbeat_freshness()

    assert is_fresh is False
    assert alerts == [("scheduler_heartbeat_missed", "Scheduler heartbeat is missing.")]


@pytest.mark.asyncio
async def test_scheduler_heartbeat_detects_fresh_key(redis_client: Redis) -> None:
    await write_scheduler_heartbeat()

    assert await redis_client.exists(HEARTBEAT_KEY) == 1
    assert await check_scheduler_heartbeat_freshness(max_age_seconds=300) is True


@pytest.mark.asyncio
async def test_app_lifespan_starts_scheduler_and_writes_initial_heartbeat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    scheduler = SimpleNamespace(
        start=lambda: events.append("start"),
        shutdown=lambda wait=False: events.append(f"shutdown:{wait}"),
    )

    async def fake_heartbeat() -> None:
        events.append("heartbeat")

    monkeypatch.setattr(main_app, "create_scheduler", lambda: scheduler, raising=False)
    monkeypatch.setattr(main_app, "write_scheduler_heartbeat", fake_heartbeat, raising=False)

    async with main_app.lifespan(main_app.app):
        assert main_app.app.state.scheduler is scheduler

    assert events == ["heartbeat", "start", "shutdown:False"]
