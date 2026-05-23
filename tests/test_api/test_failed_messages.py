from __future__ import annotations

from collections.abc import AsyncGenerator
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.main import app
from app.models import AuditLog, Clinic, FailedMessage
from app.services.auth import create_access_token


@pytest_asyncio.fixture
async def api_client(db_session: AsyncSession) -> AsyncGenerator[httpx.AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def create_failed_message_fixture(
    db_session: AsyncSession,
) -> tuple[Clinic, FailedMessage]:
    clinic = Clinic(
        id=uuid4(),
        name="Failed Diagnostics",
        owner_name="Owner",
        whatsapp_number="+918100005001",
        owner_whatsapp="+919000005001",
        clinic_type="diagnostic",
        settings={"wa_phone_number_id": "phone-failed-5001"},
    )
    failed = FailedMessage(
        clinic_id=clinic.id,
        whatsapp_number="+917700005001",
        wa_message_id="wamid.failed.1",
        raw_payload=failed_payload(),
        error="Flow crashed",
    )
    db_session.add_all([clinic, failed])
    await db_session.commit()
    return clinic, failed


def failed_payload() -> dict[str, object]:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "entry-id",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+918100005001",
                                "phone_number_id": "phone-failed-5001",
                            },
                            "messages": [
                                {
                                    "from": "917700005001",
                                    "id": "wamid.failed.1",
                                    "timestamp": "1710000000",
                                    "text": {"body": "report status"},
                                    "type": "text",
                                },
                            ],
                        },
                    },
                ],
            },
        ],
    }


def auth_headers(clinic: Clinic) -> dict[str, str]:
    token = create_access_token(clinic.owner_whatsapp, str(clinic.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_list_failed_messages_returns_unresolved_for_clinic(
    db_session: AsyncSession,
    api_client: httpx.AsyncClient,
) -> None:
    clinic, failed = await create_failed_message_fixture(db_session)
    db_session.add(
        FailedMessage(
            clinic_id=clinic.id,
            whatsapp_number="+917700005002",
            wa_message_id="wamid.resolved",
            raw_payload=failed_payload(),
            resolved=True,
        ),
    )
    await db_session.commit()

    response = await api_client.get(
        f"/api/v1/clinics/{clinic.id}/failed-messages",
        headers=auth_headers(clinic),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] == 1
    assert body["data"][0]["id"] == str(failed.id)
    assert body["data"][0]["wa_message_id"] == "wamid.failed.1"
    assert body["data"][0]["error"] == "Flow crashed"
    assert body["data"][0]["retry_count"] == 0
    assert body["data"][0]["resolved"] is False


@pytest.mark.asyncio
async def test_retry_failed_message_replays_marks_resolved_and_audits(
    db_session: AsyncSession,
    api_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clinic, failed = await create_failed_message_fixture(db_session)
    replayed: list[str] = []

    async def fake_replay_failed_payload(failed_message: FailedMessage, db: AsyncSession) -> None:
        replayed.append(str(failed_message.id))

    monkeypatch.setattr(
        "app.api.v1.failed_messages.replay_failed_payload",
        fake_replay_failed_payload,
    )

    response = await api_client.post(
        f"/api/v1/clinics/{clinic.id}/failed-messages/{failed.id}/retry",
        headers=auth_headers(clinic),
    )

    refreshed = (
        await db_session.execute(
            select(FailedMessage).where(
                FailedMessage.clinic_id == clinic.id,
                FailedMessage.id == failed.id,
            ),
        )
    ).scalar_one()
    audit = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.clinic_id == clinic.id,
                AuditLog.action == "failed_message.retried",
                AuditLog.entity_id == failed.id,
            ),
        )
    ).scalar_one()

    assert response.status_code == 200
    assert response.json()["data"]["resolved"] is True
    assert replayed == [str(failed.id)]
    assert refreshed.resolved is True
    assert refreshed.retry_count == 1
    assert refreshed.error is None
    assert refreshed.last_retry_at is not None
    assert audit.actor_type == "owner"


@pytest.mark.asyncio
async def test_retry_failed_message_keeps_unresolved_on_replay_failure(
    db_session: AsyncSession,
    api_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clinic, failed = await create_failed_message_fixture(db_session)

    async def fake_replay_failed_payload(failed_message: FailedMessage, db: AsyncSession) -> None:
        raise RuntimeError("still broken")

    monkeypatch.setattr(
        "app.api.v1.failed_messages.replay_failed_payload",
        fake_replay_failed_payload,
    )

    response = await api_client.post(
        f"/api/v1/clinics/{clinic.id}/failed-messages/{failed.id}/retry",
        headers=auth_headers(clinic),
    )

    refreshed = (
        await db_session.execute(
            select(FailedMessage).where(
                FailedMessage.clinic_id == clinic.id,
                FailedMessage.id == failed.id,
            ),
        )
    ).scalar_one()
    body = response.json()

    assert response.status_code == 502
    assert body["error"]["code"] == "FAILED_MESSAGE_RETRY_FAILED"
    assert body["error"]["request_id"]
    assert refreshed.resolved is False
    assert refreshed.retry_count == 1
    assert refreshed.error == "still broken"
