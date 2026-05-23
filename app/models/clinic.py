from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.appointment_slot import AppointmentSlot
    from app.models.broadcast import Broadcast
    from app.models.conversation import ConversationSession
    from app.models.doctor import Doctor
    from app.models.patient import Patient
    from app.models.recall_schedule import RecallSchedule
    from app.models.review import Review
    from app.models.test import Test
    from app.models.test_booking import TestBooking


class Clinic(SoftDeleteMixin, Base):
    __tablename__ = "clinics"
    __table_args__ = (
        CheckConstraint(
            "clinic_type IN ('gp','diagnostic','eye','dental','physio','other')",
            name="ck_clinics_clinic_type",
        ),
        CheckConstraint(
            "plan IN ('starter','clinic','diagnostic','chain')",
            name="ck_clinics_plan",
        ),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    owner_name: Mapped[str | None] = mapped_column(Text)
    clinic_type: Mapped[str | None] = mapped_column(String(32))
    whatsapp_number: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    owner_whatsapp: Mapped[str] = mapped_column(Text, nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(Text)
    pincode: Mapped[str | None] = mapped_column(Text)
    google_place_id: Mapped[str | None] = mapped_column(Text)
    gbp_review_link: Mapped[str | None] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(Text, default="Asia/Kolkata", nullable=False)
    plan: Mapped[str] = mapped_column(Text, default="starter", nullable=False)
    plan_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    trial_ends_at: Mapped[datetime | None]
    settings: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict, nullable=False)

    patients: Mapped[list[Patient]] = relationship(back_populates="clinic", lazy="selectin")
    doctors: Mapped[list[Doctor]] = relationship(back_populates="clinic", lazy="selectin")
    appointment_slots: Mapped[list[AppointmentSlot]] = relationship(
        back_populates="clinic",
        lazy="selectin",
    )
    appointments: Mapped[list[Appointment]] = relationship(back_populates="clinic", lazy="selectin")
    tests: Mapped[list[Test]] = relationship(back_populates="clinic", lazy="selectin")
    test_bookings: Mapped[list[TestBooking]] = relationship(
        back_populates="clinic",
        lazy="selectin",
    )
    conversation_sessions: Mapped[list[ConversationSession]] = relationship(
        back_populates="clinic",
        lazy="selectin",
    )
    recall_schedules: Mapped[list[RecallSchedule]] = relationship(
        back_populates="clinic",
        lazy="selectin",
    )
    reviews: Mapped[list[Review]] = relationship(back_populates="clinic", lazy="selectin")
    broadcasts: Mapped[list[Broadcast]] = relationship(back_populates="clinic", lazy="selectin")
