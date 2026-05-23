from __future__ import annotations

from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AuditLog(TimestampMixin, Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        CheckConstraint(
            "actor_type IN ('patient','owner','staff','system')",
            name="ck_audit_actor_type",
        ),
        Index("idx_audit_clinic", "clinic_id", "created_at"),
    )

    clinic_id: Mapped[str | None] = mapped_column(ForeignKey("clinics.id", ondelete="SET NULL"))
    actor_id: Mapped[UUID | None]
    actor_type: Mapped[str | None] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str | None] = mapped_column(Text)
    entity_id: Mapped[UUID | None]
    diff: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    ip_address: Mapped[str | None] = mapped_column(Text)
