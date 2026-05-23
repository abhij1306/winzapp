from __future__ import annotations

from collections.abc import AsyncGenerator
from decimal import Decimal
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.main import app
from app.models import AuditLog, Clinic, Patient, Test, TestBooking
from app.services.auth import create_access_token


@pytest_asyncio.fixture
async def redis_client() -> Redis:
    client = Redis.from_url(get_settings().redis_url, decode_responses=True)
    await client.flushdb()
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()


@pytest_asyncio.fixture
async def api_client(db_session: AsyncSession) -> AsyncGenerator[httpx.AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def create_report_ready_fixture(
    db_session: AsyncSession,
    clinic_id: UUID,
    patient_phone: str,
) -> tuple[Patient, TestBooking]:
    db_session.add(
        Clinic(
            id=clinic_id,
            name="Demo Diagnostics",
            whatsapp_number="+919000000001",
            owner_whatsapp="+919000000002",
            clinic_type="diagnostic",
            settings={"wa_phone_number_id": "phone-number-id"},
        ),
    )
    patient = Patient(
        id=uuid4(),
        clinic_id=clinic_id,
        whatsapp_number=patient_phone,
        name="Anita",
        opt_in=True,
    )
    test = Test(
        id=uuid4(),
        clinic_id=clinic_id,
        name="HbA1c",
        category="Diabetes",
        price=Decimal("450.00"),
        sort_order=1,
    )
    booking = TestBooking(
        clinic_id=clinic_id,
        patient_id=patient.id,
        test_id=test.id,
        test_name="HbA1c",
        booking_type="walkin",
        status="processing",
        amount=Decimal("450.00"),
        payment_status="paid",
        payment_method="manual_offline",
    )
    db_session.add_all([patient, test, booking])
    await db_session.commit()
    return patient, booking


def auth_headers(clinic_id: UUID) -> dict[str, str]:
    token = create_access_token("+919000000002", str(clinic_id))
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_report_ready_requires_owner_auth_before_booking_lookup(
    db_session: AsyncSession,
    redis_client: Redis,
    api_client: httpx.AsyncClient,
) -> None:
    clinic_id = uuid4()
    await create_report_ready_fixture(db_session, clinic_id, "+919876543209")

    response = await api_client.post(
        "/api/v1/report-ready",
        json={
            "clinic_id": str(clinic_id),
            "patient_phone": "+919876543299",
            "test_name": "HbA1c",
            "report_pdf_url": "https://reports.example/hba1c.pdf",
        },
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


@pytest.mark.asyncio
async def test_report_ready_rejects_automatic_delivery_for_opted_out_patient(
    db_session: AsyncSession,
    redis_client: Redis,
    api_client: httpx.AsyncClient,
) -> None:
    clinic_id = uuid4()
    patient, _booking = await create_report_ready_fixture(
        db_session,
        clinic_id,
        "+919876543208",
    )
    patient.opt_in = False
    await db_session.commit()

    response = await api_client.post(
        "/api/v1/report-ready",
        headers=auth_headers(clinic_id),
        json={
            "clinic_id": str(clinic_id),
            "patient_phone": patient.whatsapp_number,
            "test_name": "HbA1c",
            "report_pdf_url": "https://reports.example/hba1c.pdf",
        },
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PATIENT_OPTED_OUT"


@pytest.mark.asyncio
async def test_report_ready_delivers_pdf_url_updates_booking_and_audits(
    db_session: AsyncSession,
    redis_client: Redis,
    api_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clinic_id = uuid4()
    patient, booking = await create_report_ready_fixture(
        db_session,
        clinic_id,
        "+919876543210",
    )
    sent_payloads = []

    async def fake_copy_from_url(report_pdf_url: str, clinic_id: str, booking_id: str) -> str:
        assert report_pdf_url == "https://reports.example/hba1c.pdf"
        return f"reports/{clinic_id}/{booking_id}/report.pdf"

    async def fake_create_signed_url(path: str, expires_in: int = 86400) -> str:
        assert expires_in == 86400
        return f"https://signed.example/{path}"

    async def fake_send_document(
        phone_number_id: str,
        to: str,
        access_token: str,
        document_url: str,
        filename: str,
        caption: str | None = None,
    ) -> dict[str, object]:
        sent_payloads.append(
            {
                "phone_number_id": phone_number_id,
                "to": to,
                "document_url": document_url,
                "filename": filename,
                "caption": caption,
            },
        )
        return {"messages": [{"id": "wamid.report"}]}

    monkeypatch.setattr("app.services.storage.copy_report_from_url", fake_copy_from_url)
    monkeypatch.setattr("app.services.storage.create_signed_url", fake_create_signed_url)
    monkeypatch.setattr("app.services.whatsapp_sender.send_document", fake_send_document)

    response = await api_client.post(
        "/api/v1/report-ready",
        headers=auth_headers(clinic_id),
        json={
            "clinic_id": str(clinic_id),
            "patient_phone": patient.whatsapp_number,
            "test_name": "HbA1c",
            "report_pdf_url": "https://reports.example/hba1c.pdf",
        },
    )

    refreshed_booking = (
        await db_session.execute(
            select(TestBooking).where(
                TestBooking.clinic_id == clinic_id,
                TestBooking.id == booking.id,
            ),
        )
    ).scalar_one()
    audit = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.clinic_id == clinic_id,
                AuditLog.action == "report.delivered",
            ),
        )
    ).scalar_one()

    assert response.status_code == 200
    assert response.json()["data"] == {
        "booking_id": str(booking.id),
        "status": "delivered",
        "report_file_path": f"reports/{clinic_id}/{booking.id}/report.pdf",
    }
    assert sent_payloads == [
        {
            "phone_number_id": "phone-number-id",
            "to": patient.whatsapp_number,
            "document_url": f"https://signed.example/reports/{clinic_id}/{booking.id}/report.pdf",
            "filename": "Report_HbA1c.pdf",
            "caption": "HbA1c report attached hai.",
        },
    ]
    assert refreshed_booking.status == "delivered"
    assert refreshed_booking.report_file_path == f"reports/{clinic_id}/{booking.id}/report.pdf"
    assert refreshed_booking.report_delivered_at is not None
    assert refreshed_booking.report_status_notified is True
    assert audit.entity_id == booking.id
    assert audit.actor_type == "system"


@pytest.mark.asyncio
async def test_report_ready_accepts_base64_pdf_payload(
    db_session: AsyncSession,
    redis_client: Redis,
    api_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clinic_id = uuid4()
    patient, booking = await create_report_ready_fixture(
        db_session,
        clinic_id,
        "+919876543211",
    )

    async def fake_upload_report_base64(
        report_pdf_base64: str,
        clinic_id: str,
        booking_id: str,
    ) -> str:
        assert report_pdf_base64 == "JVBERi0xLjQ="
        return f"reports/{clinic_id}/{booking_id}/report.pdf"

    async def fake_create_signed_url(path: str, expires_in: int = 86400) -> str:
        return f"https://signed.example/{path}"

    async def fake_send_document(
        phone_number_id: str,
        to: str,
        access_token: str,
        document_url: str,
        filename: str,
        caption: str | None = None,
    ) -> dict[str, object]:
        return {"messages": [{"id": "wamid.report"}]}

    monkeypatch.setattr("app.services.storage.upload_report_base64", fake_upload_report_base64)
    monkeypatch.setattr("app.services.storage.create_signed_url", fake_create_signed_url)
    monkeypatch.setattr("app.services.whatsapp_sender.send_document", fake_send_document)

    response = await api_client.post(
        "/api/v1/report-ready",
        headers=auth_headers(clinic_id),
        json={
            "clinic_id": str(clinic_id),
            "patient_phone": patient.whatsapp_number,
            "test_name": "HbA1c",
            "report_pdf_base64": "JVBERi0xLjQ=",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"] == {
        "booking_id": str(booking.id),
        "status": "delivered",
        "report_file_path": f"reports/{clinic_id}/{booking.id}/report.pdf",
    }


@pytest.mark.asyncio
async def test_report_ready_missing_booking_returns_error_envelope(
    db_session: AsyncSession,
    redis_client: Redis,
    api_client: httpx.AsyncClient,
) -> None:
    clinic_id = uuid4()
    await create_report_ready_fixture(db_session, clinic_id, "+919876543213")

    response = await api_client.post(
        "/api/v1/report-ready",
        headers=auth_headers(clinic_id),
        json={
            "clinic_id": str(clinic_id),
            "patient_phone": "+919876543212",
            "test_name": "HbA1c",
            "report_pdf_url": "https://reports.example/hba1c.pdf",
        },
    )

    body = response.json()

    assert response.status_code == 404
    assert body["error"]["code"] == "REPORT_BOOKING_NOT_FOUND"
    assert body["error"]["message"] == "Matching test booking was not found."
    assert body["error"]["details"] == {}
    assert body["error"]["request_id"]
