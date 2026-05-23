from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.clinic import Clinic
    from app.models.patient import Patient


class RecallSchedule(TimestampMixin, Base):
    __tablename__ = "recall_schedules"
    __table_args__ = (
        CheckConstraint(
            "trigger_type IN ('annual_checkup','hba1c_quarterly','thyroid_6month',"
            "'lipid_annual','followup','custom')",
            name="ck_recalls_trigger_type",
        ),
        CheckConstraint(
            "status IN ('pending','sent','responded','dismissed','snoozed')",
            name="ck_recalls_status",
        ),
        Index("idx_recall_pending", "trigger_at", postgresql_where="status = 'pending'"),
    )

    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinics.id", ondelete="CASCADE"), index=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id", ondelete="RESTRICT"))
    trigger_type: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_at: Mapped[datetime]
    message_template: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="pending", nullable=False)
    snoozed_until: Mapped[datetime | None]
    sent_at: Mapped[datetime | None]
    response: Mapped[str | None] = mapped_column(Text)
    reference_id: Mapped[UUID | None]

    clinic: Mapped[Clinic] = relationship(back_populates="recall_schedules", lazy="selectin")
    patient: Mapped[Patient] = relationship(back_populates="recall_schedules", lazy="selectin")
