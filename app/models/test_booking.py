from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base, SoftDeleteMixin

if TYPE_CHECKING:
    from app.models.clinic import Clinic
    from app.models.patient import Patient
    from app.models.test import Test


class TestBooking(SoftDeleteMixin, Base):
    __tablename__ = "test_bookings"
    __test__ = False
    __table_args__ = (
        CheckConstraint("booking_type IN ('walkin','home_collection')", name="ck_bookings_type"),
        CheckConstraint(
            "status IN ("
            "'booked','sample_collected','processing','report_ready','delivered','cancelled'"
            ")",
            name="ck_bookings_status",
        ),
        CheckConstraint(
            "payment_status IN ('pending','paid','partial')", name="ck_bookings_payment"
        ),
        Index(
            "idx_test_bookings_status",
            "clinic_id",
            "status",
            postgresql_where="deleted_at IS NULL",
        ),
    )

    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinics.id", ondelete="CASCADE"), index=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id", ondelete="RESTRICT"))
    test_id: Mapped[str | None] = mapped_column(ForeignKey("tests.id", ondelete="SET NULL"))
    test_name: Mapped[str] = mapped_column(Text, nullable=False)
    booking_type: Mapped[str] = mapped_column(Text, default="walkin", nullable=False)
    status: Mapped[str] = mapped_column(Text, default="booked", nullable=False)
    collection_address: Mapped[str | None] = mapped_column(Text)
    collection_lat: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    collection_lng: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    collection_slot: Mapped[datetime | None]
    technician_name: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    payment_status: Mapped[str] = mapped_column(Text, default="pending", nullable=False)
    payment_method: Mapped[str | None] = mapped_column(Text)
    report_file_path: Mapped[str | None] = mapped_column(Text)
    report_password: Mapped[str | None] = mapped_column(Text)
    report_delivered_at: Mapped[datetime | None]
    report_status_notified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fasting_reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    booked_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    clinic: Mapped[Clinic] = relationship(back_populates="test_bookings", lazy="selectin")
    patient: Mapped[Patient] = relationship(back_populates="test_bookings", lazy="selectin")
    test: Mapped[Test | None] = relationship(back_populates="test_bookings", lazy="selectin")
