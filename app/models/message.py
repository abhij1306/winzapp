from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Message(TimestampMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint("direction IN ('inbound','outbound')", name="ck_messages_direction"),
        Index("idx_messages_clinic_number", "clinic_id", "whatsapp_number", "created_at"),
    )

    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinics.id", ondelete="CASCADE"), index=True)
    whatsapp_number: Mapped[str] = mapped_column(Text, nullable=False)
    direction: Mapped[str | None] = mapped_column(Text)
    message_type: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        nullable=False,
    )
    wa_message_id: Mapped[str | None] = mapped_column(Text, unique=True)
