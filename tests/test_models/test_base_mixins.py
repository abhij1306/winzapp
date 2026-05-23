from datetime import UTC, datetime

from app.models.base import Base, SoftDeleteMixin


class MutableExample(SoftDeleteMixin, Base):
    __tablename__ = "mutable_examples"


def test_soft_delete_mixin_reports_not_deleted_without_deleted_at() -> None:
    model = MutableExample()

    assert model.is_deleted is False


def test_soft_delete_mixin_reports_deleted_when_deleted_at_is_set() -> None:
    model = MutableExample(deleted_at=datetime.now(UTC))

    assert model.is_deleted is True


def test_soft_delete_model_has_required_columns() -> None:
    columns = MutableExample.__table__.c

    assert "id" in columns
    assert "created_at" in columns
    assert "updated_at" in columns
    assert "deleted_at" in columns
    assert "deleted_by" in columns


def test_updated_at_has_server_default_and_onupdate() -> None:
    updated_at = MutableExample.__table__.c.updated_at

    assert updated_at.server_default is not None
    assert updated_at.onupdate is not None
