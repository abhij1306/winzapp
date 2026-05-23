from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ConversationSession


@dataclass(frozen=True)
class FlowMessage:
    clinic_id: UUID | str
    whatsapp_number: str
    text: str


class BaseFlow(Protocol):
    async def handle(
        self,
        session: ConversationSession | None,
        message: FlowMessage,
        db: AsyncSession,
    ) -> str:
        raise NotImplementedError
