from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.clinic import Clinic
    from app.models.doctor import Doctor


class AppointmentSlot(TimestampMixin, Base):
    __tablename__ = "appointment_slots"
    __table_args__ = (
        UniqueConstraint(
            "clinic_id", "doctor_id", "slot_datetime", name="uq_slots_clinic_doctor_time"
        ),
    )

    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinics.id", ondelete="CASCADE"), index=True)
    doctor_id: Mapped[str | None] = mapped_column(ForeignKey("doctors.id", ondelete="SET NULL"))
    slot_datetime: Mapped[datetime]
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    clinic: Mapped[Clinic] = relationship(back_populates="appointment_slots", lazy="selectin")
    doctor: Mapped[Doctor | None] = relationship(
        back_populates="appointment_slots", lazy="selectin"
    )
    appointments: Mapped[list[Appointment]] = relationship(back_populates="slot", lazy="selectin")
