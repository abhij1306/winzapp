from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PatientData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    whatsapp_number: str
    name: str | None
    age: int | None
    gender: Literal["male", "female", "other"] | None
    address: str | None
    opt_in: bool
    tags: list[str]
    last_visit_at: datetime | None
    notes: str | None


class PatientBookingData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    test_name: str
    booking_type: str
    status: str
    amount: Decimal | None
    payment_status: str
    booked_at: datetime


class PatientProfileData(PatientData):
    bookings: list[PatientBookingData]


class PatientResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: PatientData


class PatientProfileResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: PatientProfileData


class PatientUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1)
    age: int | None = Field(default=None, ge=0, le=130)
    gender: Literal["male", "female", "other"] | None = None
    address: str | None = None
    opt_in: bool | None = None
    tags: list[str] | None = None
    notes: str | None = None
