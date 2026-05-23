from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class FailedMessage(TimestampMixin, Base):
    __tablename__ = "failed_messages"

    clinic_id: Mapped[str | None] = mapped_column(ForeignKey("clinics.id", ondelete="SET NULL"))
    whatsapp_number: Mapped[str | None] = mapped_column(Text)
    wa_message_id: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_retry_at: Mapped[datetime | None]
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
