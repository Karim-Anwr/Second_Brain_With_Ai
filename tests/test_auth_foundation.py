"""Focused static tests for Phase 2.3A cryptography and refresh-token persistence."""

from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID

from app.auth.passwords import hash_password, verify_password
from app.auth.refresh_tokens import hash_refresh_token, verify_refresh_token
from app.core.config import Settings
from app.db.models.refresh_token_session import RefreshTokenSession
from app.db.repositories.refresh_token_session import RefreshTokenSessionRepository


TEST_HASH_SECRET = "test-only-refresh-token-hash-secret"
TEST_REFRESH_TOKEN = "opaque-refresh-token-value-for-tests"


def _digest(token: str = TEST_REFRESH_TOKEN) -> str:
    return hash_refresh_token(token, secret=TEST_HASH_SECRET)


def _load_refresh_token_migration():
    project_root = Path(__file__).resolve().parents[1]
    migration_path = project_root / "alembic" / "versions" / "20260823_0002_add_refresh_token_sessions.py"
    spec = importlib.util.spec_from_file_location("phase23a_refresh_token_migration", migration_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_argon2id_password_hashes_are_not_plaintext_and_verify_independently():
    password = "correct horse battery staple"
    first_hash = hash_password(password)
    second_hash = hash_password(password)

    assert first_hash.startswith("$argon2id$")
    assert first_hash != password
    assert first_hash != second_hash
    assert verify_password(password, first_hash) is True
    assert verify_password("incorrect password", first_hash) is False


def test_password_verification_rejects_malformed_hashes_without_raising():
    assert verify_password("password", "not-a-valid-argon2-hash") is False
    assert verify_password("password", "") is False


def test_refresh_token_digest_is_not_raw_and_verifies_only_the_correct_token():
    token_hash = _digest()

    assert token_hash != TEST_REFRESH_TOKEN
    assert len(token_hash) == 64
    assert verify_refresh_token(TEST_REFRESH_TOKEN, token_hash, secret=TEST_HASH_SECRET) is True
    assert verify_refresh_token("different-opaque-token", token_hash, secret=TEST_HASH_SECRET) is False
    assert verify_refresh_token(TEST_REFRESH_TOKEN, "malformed", secret=TEST_HASH_SECRET) is False


def test_refresh_token_hashing_uses_shared_settings_and_rejects_weak_secrets(monkeypatch):
    monkeypatch.setenv("REFRESH_TOKEN_HASH_SECRET", TEST_HASH_SECRET)
    assert Settings().refresh_token_hash_secret == TEST_HASH_SECRET
    with pytest.raises(ValueError, match="at least 32 characters"):
        hash_refresh_token(TEST_REFRESH_TOKEN, secret="too-short")


def test_refresh_token_session_metadata_declares_native_uuid_fk_constraints_and_indexes():
    table = RefreshTokenSession.__table__

    assert isinstance(table.c.id.type, PostgreSQLUUID)
    assert isinstance(table.c.user_id.type, PostgreSQLUUID)
    assert table.c.token_hash.type.length == 64
    assert table.c.token_hash.nullable is False
    assert table.c.expires_at.nullable is False
    assert table.c.revoked_at.nullable is True
    assert table.c.replaced_by_session_id.nullable is True
    assert all(isinstance(table.c[column_name].type, DateTime) for column_name in ("created_at", "expires_at", "revoked_at"))
    assert all(table.c[column_name].type.timezone is True for column_name in ("created_at", "expires_at", "revoked_at"))
    assert any(
        isinstance(constraint, ForeignKeyConstraint)
        and constraint.name == "fk_refresh_token_sessions_user_id"
        and constraint.ondelete == "RESTRICT"
        for constraint in table.constraints
    )
    assert {
        "uq_refresh_token_sessions_token_hash",
        "uq_refresh_token_sessions_replacement",
    }.issubset(
        {
            constraint.name
            for constraint in table.constraints
            if isinstance(constraint, UniqueConstraint)
        }
    )
    assert {
        "ck_refresh_token_sessions_token_hash",
        "ck_refresh_token_sessions_expiry_after_created",
        "ck_refresh_token_sessions_no_self_replacement",
    }.issubset(
        {
            constraint.name
            for constraint in table.constraints
            if isinstance(constraint, CheckConstraint)
        }
    )
    assert {
        "ix_refresh_token_sessions_user_id",
        "ix_refresh_token_sessions_expires_at",
        "ix_refresh_token_sessions_revoked_at",
    }.issubset({index.name for index in table.indexes})
    assert "refresh_token" not in set(table.columns.keys()) - {"token_hash"}


def test_refresh_token_session_model_rejects_non_digest_values():
    with pytest.raises(ValueError, match="token_hash"):
        RefreshTokenSession(
            user_id=uuid4(),
            token_hash=TEST_REFRESH_TOKEN,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )


def test_refresh_token_repository_flushes_without_committing_and_supports_lookup_and_revocation():
    class FakeSession:
        def __init__(self):
            self.added = None
            self.flush_calls = 0
            self.commit_called = False
            self.statement = None

        def add(self, value):
            self.added = value

        def flush(self):
            self.flush_calls += 1

        def commit(self):
            self.commit_called = True

        def scalar(self, statement):
            self.statement = statement
            return self.added

    session = FakeSession()
    repository = RefreshTokenSessionRepository(session)
    token_hash = _digest()
    created = repository.create(
        user_id=UUID("00000000-0000-0000-0000-000000000001"),
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )

    assert created is session.added
    assert session.flush_calls == 1
    assert session.commit_called is False
    assert repository.get_by_token_hash(token_hash) is created
    assert repository.get_active_by_token_hash(token_hash) is created
    assert "now()" in str(session.statement.compile(compile_kwargs={"literal_binds": True})).lower()
    revoked = repository.revoke(created)
    assert revoked.revoked_at is not None
    assert session.flush_calls == 2
    assert session.commit_called is False


def test_refresh_token_repository_rejects_invalid_digest_and_naive_expiration():
    class FakeSession:
        def add(self, _value):
            raise AssertionError("invalid input must not be staged")

    repository = RefreshTokenSessionRepository(FakeSession())
    with pytest.raises(ValueError, match="token_hash"):
        repository.create(user_id=uuid4(), token_hash="raw-token", expires_at=datetime.now(timezone.utc))
    with pytest.raises(ValueError, match="timezone-aware"):
        repository.create(user_id=uuid4(), token_hash=_digest(), expires_at=datetime.now())
    assert repository.get_by_token_hash("raw-token") is None
    assert repository.get_active_by_token_hash("raw-token") is None


def test_refresh_token_migration_has_expected_metadata_and_reversible_operations(monkeypatch):
    migration = _load_refresh_token_migration()

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

    assert migration.revision == "20260823_0002"
    assert migration.down_revision == "20260822_0001"
    assert migration.branch_labels is None
    assert migration.depends_on is None

    migration.upgrade()
    migration.downgrade()

    assert operations.calls[0][0] == "create_table"
    assert operations.calls[0][1][0] == "refresh_token_sessions"
    assert [call[0] for call in operations.calls[1:4]] == ["create_index", "create_index", "create_index"]
    assert [call[0] for call in operations.calls[4:]] == ["drop_index", "drop_index", "drop_index", "drop_table"]
