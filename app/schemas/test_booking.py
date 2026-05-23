from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

BookingType = Literal["walkin", "home_collection"]
BookingStatus = Literal[
    "booked",
    "sample_collected",
    "processing",
    "report_ready",
    "delivered",
    "cancelled",
]
PaymentStatus = Literal["pending", "paid", "partial"]


class TestBookingData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    patient_id: str
    patient_name: str | None
    patient_whatsapp: str
    test_id: str | None
    test_name: str
    booking_type: BookingType
    status: BookingStatus
    collection_address: str | None
    collection_slot: datetime | None
    technician_name: str | None
    amount: Decimal | None
    payment_status: PaymentStatus
    payment_method: str | None
    report_file_path: str | None
    report_delivered_at: datetime | None
    booked_at: datetime
    notes: str | None


class TestBookingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: TestBookingData


class TestBookingCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: str
    test_id: str | None = None
    test_name: str | None = Field(default=None, min_length=1)
    booking_type: BookingType = "walkin"
    collection_address: str | None = None
    collection_slot: datetime | None = None
    technician_name: str | None = None
    amount: Decimal | None = Field(default=None, ge=0)
    payment_status: PaymentStatus = "pending"
    payment_method: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def require_test_reference(self) -> TestBookingCreateRequest:
        if self.test_id is None and self.test_name is None:
            raise ValueError("Provide test_id or test_name.")
        return self


class TestBookingUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: BookingStatus | None = None
    booking_type: BookingType | None = None
    collection_address: str | None = None
    collection_slot: datetime | None = None
    technician_name: str | None = None
    amount: Decimal | None = Field(default=None, ge=0)
    payment_status: PaymentStatus | None = None
    payment_method: str | None = None
    report_file_path: str | None = None
    notes: str | None = None
