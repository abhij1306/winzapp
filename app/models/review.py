from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.clinic import Clinic
    from app.models.patient import Patient


class Review(TimestampMixin, Base):
    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint(
            "source IN ('google','practo','justdial') OR source IS NULL", name="ck_reviews_source"
        ),
    )

    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinics.id", ondelete="CASCADE"), index=True)
    patient_id: Mapped[str | None] = mapped_column(ForeignKey("patients.id", ondelete="SET NULL"))
    source: Mapped[str | None] = mapped_column(Text)
    rating: Mapped[Decimal | None] = mapped_column(Numeric(2, 1))
    review_text: Mapped[str | None] = mapped_column(Text)
    reviewer_name: Mapped[str | None] = mapped_column(Text)
    google_review_id: Mapped[str | None] = mapped_column(Text)
    draft_reply: Mapped[str | None] = mapped_column(Text)
    reply_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reply_sent_at: Mapped[datetime | None]
    fetched_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    clinic: Mapped[Clinic] = relationship(back_populates="reviews", lazy="selectin")
    patient: Mapped[Patient | None] = relationship(back_populates="reviews", lazy="selectin")
