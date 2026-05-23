from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog
from app.utils.logger import get_logger

ALLOWED_ACTOR_TYPES = {"patient", "owner", "staff", "system"}
logger = get_logger(__name__)


async def write_audit(
    db: AsyncSession,
    clinic_id: UUID | str | None,
    actor_type: str,
    action: str,
    entity_type: str | None,
    entity_id: UUID | None,
    diff: dict[str, object],
    actor_id: UUID | None = None,
    ip_address: str | None = None,
) -> None:
    if actor_type not in ALLOWED_ACTOR_TYPES:
        logger.error("audit.invalid_actor_type", actor_type=actor_type, action=action)
        return

    try:
        db.add(
            AuditLog(
                clinic_id=str(clinic_id) if clinic_id is not None else None,
                actor_id=actor_id,
                actor_type=actor_type,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                diff=diff,
                ip_address=ip_address,
            ),
        )
        await db.commit()
    except Exception as exc:
        logger.error("audit.write_failed", action=action, error=str(exc))
        await rollback_quietly(db)


async def rollback_quietly(db: AsyncSession) -> None:
    try:
        await db.rollback()
    except Exception as exc:
        logger.error("audit.rollback_failed", error=str(exc))
