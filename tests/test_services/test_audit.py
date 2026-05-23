from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Clinic
from app.services.audit import write_audit


@pytest.mark.asyncio
async def test_write_audit_inserts_row(db_session: AsyncSession) -> None:
    clinic_id = uuid4()
    entity_id = uuid4()
    db_session.add(
        Clinic(
            id=clinic_id,
            name="Demo Lab",
            whatsapp_number="+919777777777",
            owner_whatsapp="+918777777777",
            settings={},
        ),
    )
    await db_session.commit()

    await write_audit(
        db=db_session,
        clinic_id=clinic_id,
        actor_type="system",
        action="test.created",
        entity_type="test",
        entity_id=entity_id,
        diff={"before": None, "after": {"name": "CBC"}},
    )

    row = (
        await db_session.execute(select(AuditLog).where(AuditLog.action == "test.created"))
    ).scalar_one()
    assert row.clinic_id == clinic_id
    assert row.actor_type == "system"
    assert row.entity_id == entity_id


@pytest.mark.asyncio
async def test_write_audit_does_not_raise_when_db_write_fails() -> None:
    class FailingDb:
        def add(self, _row: object) -> None:
            raise RuntimeError("db unavailable")

        async def commit(self) -> None:
            raise RuntimeError("db unavailable")

        async def rollback(self) -> None:
            return None

    await write_audit(
        db=FailingDb(),  # type: ignore[arg-type]
        clinic_id=uuid4(),
        actor_type="system",
        action="test.created",
        entity_type="test",
        entity_id=uuid4(),
        diff={"before": None, "after": None},
    )
