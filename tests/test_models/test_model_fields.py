from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

from app.models import (
    Appointment,
    AppointmentSlot,
    AuditLog,
    Broadcast,
    Clinic,
    ConversationSession,
    Doctor,
    FailedMessage,
    Message,
    Patient,
    RecallSchedule,
    Review,
    Test,
    TestBooking,
)

EXPECTED_TABLES = {
    "clinics",
    "doctors",
    "patients",
    "appointment_slots",
    "appointments",
    "tests",
    "test_bookings",
    "conversation_sessions",
    "messages",
    "failed_messages",
    "audit_log",
    "recall_schedules",
    "reviews",
    "broadcasts",
}


def test_all_models_are_importable_with_expected_table_names() -> None:
    models = [
        Clinic,
        Doctor,
        Patient,
        AppointmentSlot,
        Appointment,
        Test,
        TestBooking,
        ConversationSession,
        Message,
        FailedMessage,
        AuditLog,
        RecallSchedule,
        Review,
        Broadcast,
    ]

    assert {model.__tablename__ for model in models} == EXPECTED_TABLES


def test_each_model_can_be_instantiated_with_required_fields() -> None:
    instances = [
        Clinic(name="Demo Lab", whatsapp_number="+919999999999", owner_whatsapp="+919888888888"),
        Doctor(clinic_id="00000000-0000-0000-0000-000000000001", name="Dr Demo"),
        Patient(clinic_id="00000000-0000-0000-0000-000000000001", whatsapp_number="+919999999999"),
        AppointmentSlot(
            clinic_id="00000000-0000-0000-0000-000000000001",
            slot_datetime="2026-05-23T09:00:00+05:30",
        ),
        Appointment(
            clinic_id="00000000-0000-0000-0000-000000000001",
            patient_id="00000000-0000-0000-0000-000000000002",
            appointment_at="2026-05-23T09:00:00+05:30",
        ),
        Test(clinic_id="00000000-0000-0000-0000-000000000001", name="CBC"),
        TestBooking(
            clinic_id="00000000-0000-0000-0000-000000000001",
            patient_id="00000000-0000-0000-0000-000000000002",
            test_name="CBC",
        ),
        ConversationSession(
            clinic_id="00000000-0000-0000-0000-000000000001",
            whatsapp_number="+919999999999",
        ),
        Message(
            clinic_id="00000000-0000-0000-0000-000000000001",
            whatsapp_number="+919999999999",
        ),
        FailedMessage(raw_payload={"entry": []}),
        AuditLog(action="test.created"),
        RecallSchedule(
            clinic_id="00000000-0000-0000-0000-000000000001",
            patient_id="00000000-0000-0000-0000-000000000002",
            trigger_type="hba1c_quarterly",
            trigger_at="2026-08-23T09:00:00+05:30",
        ),
        Review(clinic_id="00000000-0000-0000-0000-000000000001"),
        Broadcast(clinic_id="00000000-0000-0000-0000-000000000001", message="Hello"),
    ]

    assert len(instances) == 14


def test_clinic_settings_uses_jsonb() -> None:
    assert isinstance(Clinic.__table__.c.settings.type, JSONB)


def test_patient_has_unique_constraint_on_clinic_id_and_whatsapp_number() -> None:
    unique_constraints = [
        constraint
        for constraint in Patient.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    ]

    assert any(
        {column.name for column in constraint.columns} == {"clinic_id", "whatsapp_number"}
        for constraint in unique_constraints
    )
