"""Focused static tests for the Phase 2.2 PostgreSQL User Model foundation."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import CheckConstraint, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID

from app.db.email import canonicalize_email
from app.db.models.user import User
from app.db.repositories.user import UserRepository
from app.schemas.user import UserCreate, UserRecord


def _user_input(**overrides) -> UserCreate:
    values = {
        "email": "person@example.com",
        "password_hash": "$argon2id$prepared-storage-value",
        "display_name": "Person",
        "is_active": True,
    }
    values.update(overrides)
    return UserCreate(**values)


def _load_users_migration():
    project_root = Path(__file__).resolve().parents[1]
    migration_path = project_root / "alembic" / "versions" / "20260822_0001_add_users_table.py"
    spec = importlib.util.spec_from_file_location("phase22_users_migration", migration_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("raw_email", "canonical_email"),
    [
        ("  Person@Example.COM  ", "person@example.com"),
        ("first.last+label@sub.example.co.uk", "first.last+label@sub.example.co.uk"),
    ],
)
def test_email_canonicalization_is_trimmed_lowercase_and_accepts_normal_addresses(raw_email, canonical_email):
    assert canonicalize_email(raw_email) == canonical_email
    assert _user_input(email=raw_email).email == canonical_email


@pytest.mark.parametrize("malformed_email", ["not-an-email", "@example.com", "person@"])
def test_email_canonicalization_rejects_blank_and_malformed_addresses(malformed_email):
    with pytest.raises(ValueError, match="email must not be blank"):
        canonicalize_email("  ")
    with pytest.raises(ValueError, match="email must be a valid address"):
        canonicalize_email(malformed_email)
    with pytest.raises(ValueError, match="email must be a valid address"):
        _user_input(email=malformed_email)
    with pytest.raises(ValueError, match="email must be a valid address"):
        User(
            email=malformed_email,
            password_hash="$argon2id$prepared-storage-value",
            display_name="Person",
        )


def test_user_metadata_declares_postgresql_uuid_duplicate_email_constraint_and_indexes():
    table = User.__table__

    assert isinstance(table.c.id.type, PostgreSQLUUID)
    assert table.c.id.type.as_uuid is True
    assert table.c.email.type.length == 320
    assert any(
        isinstance(constraint, UniqueConstraint)
        and constraint.name == "uq_users_email"
        and tuple(column.name for column in constraint.columns) == ("email",)
        for constraint in table.constraints
    )
    assert {
        "ck_users_email_canonical",
        "ck_users_email_not_blank",
        "ck_users_password_hash_not_blank",
        "ck_users_display_name_not_blank",
    }.issubset(
        {
            constraint.name
            for constraint in table.constraints
            if isinstance(constraint, CheckConstraint)
        }
    )
    assert {"ix_users_is_active", "ix_users_created_at"}.issubset({index.name for index in table.indexes})


def test_uuid_and_timezone_aware_timestamp_metadata_are_configured():
    table = User.__table__
    uuid_default = table.c.id.default

    assert uuid_default is not None
    assert uuid_default.is_callable is True
    assert isinstance(uuid_default.arg(None), UUID)
    for column_name in ("created_at", "updated_at"):
        column = table.c[column_name]
        assert isinstance(column.type, DateTime)
        assert column.type.timezone is True
        assert column.server_default is not None
    assert table.c.updated_at.onupdate is not None


def test_user_dto_and_model_support_active_and_inactive_state_without_plaintext_passwords():
    active = _user_input()
    inactive = _user_input(email="inactive@example.com", is_active=False)
    model = User(
        email="  MODEL@EXAMPLE.COM  ",
        password_hash=active.password_hash,
        display_name=active.display_name,
        is_active=False,
    )

    assert active.is_active is True
    assert inactive.is_active is False
    assert model.email == "model@example.com"
    assert model.is_active is False
    assert "password" not in set(User.__table__.columns.keys()) - {"password_hash"}
    assert "password_hash" not in UserRecord.model_fields


def test_user_repository_flushes_canonicalized_persistence_input_and_queries_canonical_email():
    class FakeSession:
        def __init__(self):
            self.added = None
            self.flush_called = False
            self.statement = None

        def add(self, value):
            self.added = value

        def flush(self):
            self.flush_called = True

        def get(self, model, user_id):
            assert model is User
            return user_id

        def scalar(self, statement):
            self.statement = statement
            return self.added

    session = FakeSession()
    repository = UserRepository(session)
    created = repository.create(_user_input(email="  Person@Example.COM  "))
    found = repository.get_by_email(" PERSON@EXAMPLE.COM ")

    assert session.flush_called is True
    assert created is session.added
    assert created.email == "person@example.com"
    assert found is created
    assert "person@example.com" in str(session.statement.compile(compile_kwargs={"literal_binds": True}))
    user_id = UUID("00000000-0000-0000-0000-000000000001")
    assert repository.get_by_id(user_id) == user_id


def test_users_migration_has_expected_revision_metadata_and_reversible_operations(monkeypatch):
    migration = _load_users_migration()

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

    operations = FakeOperations()
    monkeypatch.setattr(migration, "op", operations)

    assert migration.revision == "20260822_0001"
    assert migration.down_revision is None
    assert migration.branch_labels is None
    assert migration.depends_on is None

    migration.upgrade()
    migration.downgrade()

    assert operations.calls[0][0] == "create_table"
    assert operations.calls[0][1][0] == "users"
    assert [call[0] for call in operations.calls[1:3]] == ["create_index", "create_index"]
    assert [call[0] for call in operations.calls[3:]] == ["drop_index", "drop_index", "drop_table"]
