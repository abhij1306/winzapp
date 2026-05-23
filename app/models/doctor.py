from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.appointment_slot import AppointmentSlot
    from app.models.clinic import Clinic


class Doctor(SoftDeleteMixin, Base):
    __tablename__ = "doctors"

    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinics.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    specialty: Mapped[str | None] = mapped_column(Text)
    whatsapp_number: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    slot_duration: Mapped[int] = mapped_column(Integer, default=20, nullable=False)

    clinic: Mapped[Clinic] = relationship(back_populates="doctors", lazy="selectin")
    appointment_slots: Mapped[list[AppointmentSlot]] = relationship(
        back_populates="doctor",
        lazy="selectin",
    )
    appointments: Mapped[list[Appointment]] = relationship(back_populates="doctor", lazy="selectin")
