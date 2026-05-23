from __future__ import annotations

from collections.abc import AsyncGenerator
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.main import app
from app.models import AuditLog, Clinic, Patient, Test, TestBooking
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


async def create_pending_report_fixture(
    db_session: AsyncSession,
    owner_whatsapp: str = "+919000002001",
) -> tuple[Clinic, Patient, TestBooking]:
    suffix = owner_whatsapp[-4:]
    clinic = Clinic(
        id=uuid4(),
        name="Ops Diagnostics",
        owner_name="Owner",
        whatsapp_number=f"+91810000{suffix}",
        owner_whatsapp=owner_whatsapp,
        clinic_type="diagnostic",
        settings={"wa_phone_number_id": f"phone-report-{suffix}"},
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
        category="Diabetes",
    )
    booking = TestBooking(
        clinic_id=clinic.id,
        patient=patient,
        test=test,
        test_name="HbA1c",
        booking_type="walkin",
        status="processing",
        amount=Decimal("450.00"),
        payment_status="paid",
    )
    db_session.add_all([clinic, patient, test, booking])
    await db_session.commit()
    return clinic, patient, booking


def auth_headers(clinic: Clinic) -> dict[str, str]:
    token = create_access_token(clinic.owner_whatsapp, str(clinic.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_upload_report_pdf_delivers_document_updates_booking_and_audits(
    db_session: AsyncSession,
    api_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clinic, patient, booking = await create_pending_report_fixture(db_session)
    sent_payloads: list[dict[str, object]] = []

    async def fake_upload_report_pdf(pdf_bytes: bytes, clinic_id: str, booking_id: str) -> str:
        assert pdf_bytes == b"%PDF-1.4 dashboard upload"
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
        return {"messages": [{"id": "wamid.report-upload"}]}

    monkeypatch.setattr("app.services.storage.upload_report_pdf", fake_upload_report_pdf)
    monkeypatch.setattr("app.services.storage.create_signed_url", fake_create_signed_url)
    monkeypatch.setattr("app.services.whatsapp_sender.send_document", fake_send_document)

    response = await api_client.post(
        f"/api/v1/clinics/{clinic.id}/test-bookings/{booking.id}/report-upload",
        headers=auth_headers(clinic),
        files={"report_pdf": ("hba1c.pdf", b"%PDF-1.4 dashboard upload", "application/pdf")},
    )

    assert response.status_code == 200

    refreshed = (
        await db_session.execute(
            select(TestBooking).where(
                TestBooking.clinic_id == clinic.id,
                TestBooking.id == booking.id,
            ),
        )
    ).scalar_one()
    audit = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.clinic_id == clinic.id,
                AuditLog.action == "report.delivered",
                AuditLog.entity_id == booking.id,
            ),
        )
    ).scalar_one()

    assert response.json()["data"] == {
        "booking_id": str(booking.id),
        "status": "delivered",
        "report_file_path": f"reports/{clinic.id}/{booking.id}/report.pdf",
    }
    assert sent_payloads == [
        {
            "phone_number_id": "phone-report-2001",
            "to": patient.whatsapp_number,
            "document_url": f"https://signed.example/reports/{clinic.id}/{booking.id}/report.pdf",
            "filename": "Report_HbA1c.pdf",
            "caption": "HbA1c report attached hai.",
        },
    ]
    assert refreshed.status == "delivered"
    assert refreshed.report_status_notified is True
    assert refreshed.report_delivered_at is not None
    assert audit.actor_type == "owner"


@pytest.mark.asyncio
async def test_upload_report_rejects_non_pdf_file(
    db_session: AsyncSession,
    api_client: httpx.AsyncClient,
) -> None:
    clinic, _patient, booking = await create_pending_report_fixture(db_session)

    response = await api_client.post(
        f"/api/v1/clinics/{clinic.id}/test-bookings/{booking.id}/report-upload",
        headers=auth_headers(clinic),
        files={"report_pdf": ("hba1c.txt", b"not a pdf", "text/plain")},
    )

    body = response.json()

    assert response.status_code == 400
    assert body["error"]["code"] == "REPORT_FILE_INVALID"
    assert body["error"]["request_id"]


@pytest.mark.asyncio
async def test_upload_report_rejects_cross_clinic_booking(
    db_session: AsyncSession,
    api_client: httpx.AsyncClient,
) -> None:
    clinic, _patient, _booking = await create_pending_report_fixture(db_session)
    other_clinic, _other_patient, other_booking = await create_pending_report_fixture(
        db_session,
        "+919000002002",
    )

    response = await api_client.post(
        f"/api/v1/clinics/{clinic.id}/test-bookings/{other_booking.id}/report-upload",
        headers=auth_headers(clinic),
        files={"report_pdf": ("hba1c.pdf", b"%PDF-1.4", "application/pdf")},
    )

    body = response.json()

    assert response.status_code == 404
    assert body["error"]["code"] == "BOOKING_NOT_FOUND"
    assert str(other_clinic.id) != str(clinic.id)
