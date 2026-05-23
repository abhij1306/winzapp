from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.clinic import Clinic
    from app.models.conversation import ConversationSession
    from app.models.recall_schedule import RecallSchedule
    from app.models.review import Review
    from app.models.test_booking import TestBooking


class Patient(SoftDeleteMixin, Base):
    __tablename__ = "patients"
    __table_args__ = (
        UniqueConstraint("clinic_id", "whatsapp_number", name="uq_patients_clinic_whatsapp"),
        CheckConstraint(
            "gender IN ('male','female','other') OR gender IS NULL",
            name="ck_patients_gender",
        ),
    )

    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinics.id", ondelete="CASCADE"), index=True)
    whatsapp_number: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str | None] = mapped_column(Text)
    age: Mapped[int | None] = mapped_column(Integer)
    gender: Mapped[str | None] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(Text)
    location_lat: Mapped[Decimal | None]
    location_lng: Mapped[Decimal | None]
    opt_in: Mapped[bool] = mapped_column(default=True, nullable=False)
    opt_in_at: Mapped[datetime | None]
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    last_visit_at: Mapped[datetime | None]
    notes: Mapped[str | None] = mapped_column(Text)

    clinic: Mapped[Clinic] = relationship(back_populates="patients", lazy="selectin")
    appointments: Mapped[list[Appointment]] = relationship(
        back_populates="patient", lazy="selectin"
    )
    test_bookings: Mapped[list[TestBooking]] = relationship(
        back_populates="patient", lazy="selectin"
    )
    conversation_sessions: Mapped[list[ConversationSession]] = relationship(
        back_populates="patient",
        lazy="selectin",
    )
    recall_schedules: Mapped[list[RecallSchedule]] = relationship(
        back_populates="patient",
        lazy="selectin",
    )
    reviews: Mapped[list[Review]] = relationship(back_populates="patient", lazy="selectin")
