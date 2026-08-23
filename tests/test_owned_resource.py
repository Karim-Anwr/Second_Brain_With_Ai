"""Focused static tests for the Phase 1 logical ownership authority."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID

from app.db.models.owned_resource import OwnedResource, OwnedResourceKind
from app.db.repositories.owned_resource import OwnedResourceRepository
from app.services.ownership_service import (
    OwnershipMismatchError,
    OwnershipOwnerNotFoundError,
    OwnershipResourceNotFoundError,
    OwnershipService,
)


OWNER_A = UUID("00000000-0000-0000-0000-000000000001")
OWNER_B = UUID("00000000-0000-0000-0000-000000000002")


def _owned_resource(**overrides) -> OwnedResource:
    values = {"owner_user_id": OWNER_A, "resource_kind": OwnedResourceKind.MEMORY, "resource_id": "mem_123"}
    values.update(overrides)
    return OwnedResource(**values)


def _load_owned_resources_migration():
    project_root = Path(__file__).resolve().parents[1]
    migration_path = project_root / "alembic" / "versions" / "20260823_0003_add_owned_resources.py"
    spec = importlib.util.spec_from_file_location("phase1_owned_resources_migration", migration_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_owned_resource_metadata_declares_uuid_constraints_indexes_and_restrictive_user_fk():
    table = OwnedResource.__table__

    assert isinstance(table.c.id.type, PostgreSQLUUID)
    assert table.c.id.type.as_uuid is True
    assert table.c.resource_kind.type.length == 32
    assert table.c.resource_id.type.length == 128
    assert table.c.resource_id.nullable is False
    assert table.c.owner_user_id.nullable is False
    assert any(
        isinstance(constraint, UniqueConstraint)
        and constraint.name == "uq_owned_resources_kind_resource_id"
        and tuple(column.name for column in constraint.columns) == ("resource_kind", "resource_id")
        for constraint in table.constraints
    )
    check_constraints = {
        constraint.name: str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert "ck_owned_resources_resource_kind" in check_constraints
    assert check_constraints["ck_owned_resources_resource_id_canonical_nonblank"] == (
        "resource_id = btrim(resource_id) AND btrim(resource_id) <> ''"
    )
    foreign_key = next(constraint for constraint in table.constraints if isinstance(constraint, ForeignKeyConstraint))
    assert foreign_key.name == "fk_owned_resources_owner_user_id"
    assert next(iter(foreign_key.elements)).ondelete == "RESTRICT"
    assert {"ix_owned_resources_owner_user_id", "ix_owned_resources_owner_user_id_resource_kind"}.issubset(
        {index.name for index in table.indexes}
    )


@pytest.mark.parametrize("kind", [OwnedResourceKind.MEMORY, OwnedResourceKind.FILE, OwnedResourceKind.CHAT_SESSION])
def test_supported_resource_kinds_are_accepted(kind):
    assert _owned_resource(resource_kind=kind).resource_kind == kind.value


def test_invalid_kind_and_noncanonical_resource_ids_are_rejected():
    with pytest.raises(ValueError, match="resource_kind is not supported"):
        _owned_resource(resource_kind="graph_edge")
    for resource_id in ("", "   "):
        with pytest.raises(ValueError, match="resource_id must not be blank"):
            _owned_resource(resource_id=resource_id)
    for resource_id in (" mem_123 ", "mem_123 ", " mem_123"):
        with pytest.raises(ValueError, match="resource_id must be canonical"):
            _owned_resource(resource_id=resource_id)
    with pytest.raises(ValueError, match="resource_id must not exceed 128 characters"):
        _owned_resource(resource_id="m" * 129)
    assert _owned_resource(resource_id="mem_123").resource_id == "mem_123"


def test_owner_is_immutable_and_created_timestamp_is_server_generated():
    resource = _owned_resource()
    with pytest.raises(ValueError, match="owner_user_id is immutable"):
        resource.owner_user_id = OWNER_B
    assert isinstance(OwnedResource.__table__.c.created_at.type, DateTime)
    assert OwnedResource.__table__.c.created_at.type.timezone is True
    assert OwnedResource.__table__.c.created_at.server_default is not None


def test_resource_identity_is_unique_by_kind_but_same_id_is_compatible_with_a_different_kind():
    table = OwnedResource.__table__
    unique = next(
        constraint
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint) and constraint.name == "uq_owned_resources_kind_resource_id"
    )
    assert tuple(column.name for column in unique.columns) == ("resource_kind", "resource_id")
    assert _owned_resource(resource_kind="memory", resource_id="shared").resource_id == _owned_resource(
        resource_kind="file", resource_id="shared"
    ).resource_id


def test_repository_flushes_without_committing_and_compiles_identity_queries():
    class FakeSession:
        def __init__(self):
            self.added = None
            self.flush_called = False
            self.commit_called = False
            self.scalar_result = None
            self.statement = None

        def add(self, value):
            self.added = value

        def flush(self):
            self.flush_called = True

        def commit(self):
            self.commit_called = True

        def scalar(self, statement):
            self.statement = statement
            return self.scalar_result

    session = FakeSession()
    repository = OwnedResourceRepository(session)
    created = repository.create(owner_user_id=OWNER_A, resource_kind="memory", resource_id="mem_123")
    session.scalar_result = created
    by_resource = repository.get_by_resource(resource_kind="memory", resource_id="mem_123")
    by_owner = repository.get_by_owner_and_resource(
        owner_user_id=OWNER_A, resource_kind="memory", resource_id="mem_123"
    )

    assert created is session.added
    assert session.flush_called is True
    assert session.commit_called is False
    assert by_resource is created
    assert by_owner is created
    assert "owned_resources" in str(session.statement)


def test_service_validates_active_owner_and_distinguishes_missing_and_mismatched_ownership():
    class FakeSession:
        def __init__(self):
            self.user = SimpleNamespace(id=OWNER_A, is_active=True)
            self.record = _owned_resource()
            self.added = None
            self.flush_called = False
            self.commit_called = False
            self.scalar_result = self.record

        def get(self, _model, user_id):
            return self.user if user_id == OWNER_A else None

        def add(self, value):
            self.added = value

        def flush(self):
            self.flush_called = True

        def commit(self):
            self.commit_called = True

        def scalar(self, _statement):
            return self.scalar_result

    session = FakeSession()
    service = OwnershipService(session)
    registered = service.register_resource(owner_user_id=OWNER_A, resource_kind="file", resource_id="file_123")
    assert registered.owner_user_id == OWNER_A
    assert session.commit_called is False
    assert service.require_owned_resource(owner_user_id=OWNER_A, resource_kind="memory", resource_id="mem_123") is session.record
    with pytest.raises(OwnershipMismatchError):
        service.require_owned_resource(owner_user_id=OWNER_B, resource_kind="memory", resource_id="mem_123")
    session.scalar_result = None
    with pytest.raises(OwnershipResourceNotFoundError):
        service.require_owned_resource(owner_user_id=OWNER_A, resource_kind="memory", resource_id="missing")
    with pytest.raises(OwnershipOwnerNotFoundError):
        service.register_resource(owner_user_id=OWNER_B, resource_kind="memory", resource_id="mem_other")
    session.user.is_active = False
    with pytest.raises(OwnershipOwnerNotFoundError):
        service.register_resource(owner_user_id=OWNER_A, resource_kind="memory", resource_id="mem_inactive")


def test_owned_resources_migration_has_expected_revision_metadata_and_reversible_operations(monkeypatch):
    migration = _load_owned_resources_migration()

    class FakeOperations:
        def __init__(self):
            self.calls = []

        def create_table(self, *args, **kwargs):
            self.calls.append(("create_table", args, kwargs))

        def create_index(self, *args, **kwargs):
            self.calls.append(("create_index", args, kwargs))

        def drop_index(self, *args, **kwargs):
            self.calls.append(("drop_index", args, kwargs))

        def drop_table(self, *args, **kwargs):
            self.calls.append(("drop_table", args, kwargs))

        def execute(self, *args, **kwargs):
            self.calls.append(("execute", args, kwargs))

    operations = FakeOperations()
    monkeypatch.setattr(migration, "op", operations)

    assert migration.revision == "20260823_0003"
    assert migration.down_revision == "20260823_0002"
    assert migration.branch_labels is None
    assert migration.depends_on is None

    migration.upgrade()
    migration.downgrade()

    assert operations.calls[0][0] == "create_table"
    assert operations.calls[0][1][0] == "owned_resources"
    assert [call[0] for call in operations.calls[1:3]] == ["create_index", "create_index"]
    upgrade_sql = [call[1][0] for call in operations.calls[3:5]]
    assert "CREATE FUNCTION prevent_owned_resource_owner_reassignment()" in upgrade_sql[0]
    assert "NEW.owner_user_id IS DISTINCT FROM OLD.owner_user_id" in upgrade_sql[0]
    assert "CREATE TRIGGER trg_owned_resources_owner_user_id_immutable" in upgrade_sql[1]
    assert "BEFORE UPDATE OF owner_user_id ON owned_resources" in upgrade_sql[1]
    downgrade_sql = [call[1][0] for call in operations.calls[5:7]]
    assert downgrade_sql == [
        "DROP TRIGGER IF EXISTS trg_owned_resources_owner_user_id_immutable ON owned_resources",
        "DROP FUNCTION IF EXISTS prevent_owned_resource_owner_reassignment()",
    ]
    assert [call[0] for call in operations.calls[7:]] == ["drop_index", "drop_index", "drop_table"]
