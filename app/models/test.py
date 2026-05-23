from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin

if TYPE_CHECKING:
    from app.models.clinic import Clinic
    from app.models.test_booking import TestBooking


class Test(SoftDeleteMixin, Base):
    __tablename__ = "tests"
    __test__ = False

    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinics.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    name_hindi: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    duration_hours: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    requires_fasting: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    home_collection_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    category: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    clinic: Mapped[Clinic] = relationship(back_populates="tests", lazy="selectin")
    test_bookings: Mapped[list[TestBooking]] = relationship(back_populates="test", lazy="selectin")
