from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.clinic import Clinic


class Broadcast(TimestampMixin, Base):
    __tablename__ = "broadcasts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','scheduled','sent','failed')", name="ck_broadcasts_status"
        ),
    )

    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinics.id", ondelete="CASCADE"), index=True)
    title: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    target_tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    status: Mapped[str] = mapped_column(Text, default="draft", nullable=False)
    scheduled_at: Mapped[datetime | None]
    sent_at: Mapped[datetime | None]
    recipient_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    delivered_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    clinic: Mapped[Clinic] = relationship(back_populates="broadcasts", lazy="selectin")
