from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FailedMessageData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    clinic_id: str | None
    whatsapp_number: str | None
    wa_message_id: str | None
    error: str | None
    retry_count: int
    last_retry_at: datetime | None
    resolved: bool
    created_at: datetime


class FailedMessageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: FailedMessageData
