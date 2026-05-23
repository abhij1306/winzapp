from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.clinic import Clinic
    from app.models.patient import Patient


class ConversationSession(TimestampMixin, Base):
    __tablename__ = "conversation_sessions"
    __table_args__ = (
        UniqueConstraint("clinic_id", "whatsapp_number", name="uq_sessions_clinic_whatsapp"),
        Index(
            "idx_session_active",
            "whatsapp_number",
            "clinic_id",
            postgresql_where="is_active = true",
        ),
    )

    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinics.id", ondelete="CASCADE"), index=True)
    patient_id: Mapped[str | None] = mapped_column(ForeignKey("patients.id", ondelete="SET NULL"))
    whatsapp_number: Mapped[str] = mapped_column(Text, nullable=False)
    flow: Mapped[str | None] = mapped_column(Text)
    step: Mapped[str | None] = mapped_column(Text)
    context: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict, nullable=False)
    last_message_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    clinic: Mapped[Clinic] = relationship(back_populates="conversation_sessions", lazy="selectin")
    patient: Mapped[Patient | None] = relationship(
        back_populates="conversation_sessions",
        lazy="selectin",
    )
