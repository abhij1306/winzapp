from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base, SoftDeleteMixin

if TYPE_CHECKING:
    from app.models.appointment_slot import AppointmentSlot
    from app.models.clinic import Clinic
    from app.models.doctor import Doctor
    from app.models.patient import Patient


class Appointment(SoftDeleteMixin, Base):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint(
            "appointment_type IN ('consultation','followup','walkin')",
            name="ck_appointments_type",
        ),
        CheckConstraint(
            "status IN ('confirmed','cancelled','completed','no_show','rescheduled')",
            name="ck_appointments_status",
        ),
        Index(
            "idx_appointments_clinic_date",
            "clinic_id",
            "appointment_at",
            postgresql_where="deleted_at IS NULL",
        ),
    )

    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinics.id", ondelete="CASCADE"), index=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id", ondelete="RESTRICT"))
    doctor_id: Mapped[str | None] = mapped_column(ForeignKey("doctors.id", ondelete="SET NULL"))
    slot_id: Mapped[str | None] = mapped_column(
        ForeignKey("appointment_slots.id", ondelete="SET NULL"),
    )
    appointment_type: Mapped[str] = mapped_column(Text, default="consultation", nullable=False)
    status: Mapped[str] = mapped_column(Text, default="confirmed", nullable=False)
    booked_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    appointment_at: Mapped[datetime]
    reminder_1hr_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reminder_24hr_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    review_request_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    cancelled_reason: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text, default="whatsapp", nullable=False)

    clinic: Mapped[Clinic] = relationship(back_populates="appointments", lazy="selectin")
    patient: Mapped[Patient] = relationship(back_populates="appointments", lazy="selectin")
    doctor: Mapped[Doctor | None] = relationship(back_populates="appointments", lazy="selectin")
    slot: Mapped[AppointmentSlot | None] = relationship(
        back_populates="appointments", lazy="selectin"
    )
