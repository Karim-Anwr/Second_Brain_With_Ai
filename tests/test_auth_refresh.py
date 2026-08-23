"""Focused Phase 2.3C-2 rotation tests using fake sessions; no live PostgreSQL is required."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
import pytest
from fastapi.testclient import TestClient

from app.api.routes import auth as auth_route
from app.auth.refresh_tokens import hash_refresh_token, verify_refresh_token
from app.core.config import settings
from app.core.exceptions import AuthenticationFailedException
from app.db.models.refresh_token_session import RefreshTokenSession
from app.db.models.user import User
from app.db.session import get_db
from app.main import app
from app.schemas.auth import RefreshTokenRequest
from app.services.auth_service import AuthService


TEST_JWT_SECRET = "test-jwt-signing-secret-with-at-least-thirty-two-characters"
TEST_REFRESH_SECRET = "test-refresh-secret-with-at-least-thirty-two-characters"


@pytest.fixture(autouse=True)
def configured_auth(monkeypatch):
    monkeypatch.setattr(settings, "jwt_signing_secret", TEST_JWT_SECRET)
    monkeypatch.setattr(settings, "jwt_algorithm", "HS256")
    monkeypatch.setattr(settings, "access_token_lifetime_seconds", 900)
    monkeypatch.setattr(settings, "refresh_token_hash_secret", TEST_REFRESH_SECRET)
    monkeypatch.setattr(settings, "refresh_token_lifetime_seconds", 3600)


def _user(*, active: bool = True) -> User:
    return User(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        email="person@example.com",
        password_hash="$argon2id$test-only-hash",
        display_name="Person",
        is_active=active,
    )


def _old_session(raw_token: str, *, user_id: UUID | None = None, revoked: bool = False, expired: bool = False):
    now = datetime.now(timezone.utc)
    return RefreshTokenSession(
        id=UUID("00000000-0000-0000-0000-000000000010"),
        user_id=user_id or _user().id,
        token_hash=hash_refresh_token(raw_token),
        expires_at=now - timedelta(seconds=1) if expired else now + timedelta(hours=1),
        revoked_at=now if revoked else None,
    )


class FakeSession:
    def __init__(self, *, old_session: RefreshTokenSession | None, user: User | None, fail_flush_at: int | None = None, fail_commit: bool = False):
        self.old_session = old_session
        self.user = user
        self.fail_flush_at = fail_flush_at
        self.fail_commit = fail_commit
        self.added = []
        self.flush_count = 0
        self.commit_count = 0
        self.rollback_count = 0
        self.scalar_statement = None

    def scalar(self, statement):
        self.scalar_statement = statement
        return self.old_session

    def get(self, _model, _user_id):
        return self.user

    def add(self, value):
        self.added.append(value)

    def flush(self):
        self.flush_count += 1
        if self.fail_flush_at == self.flush_count:
            raise RuntimeError("persistence failure")

    def commit(self):
        self.commit_count += 1
        if self.fail_commit:
            raise RuntimeError("commit failure")

    def rollback(self):
        self.rollback_count += 1


def _decode_access(value: str) -> dict:
    return jwt.decode(value, TEST_JWT_SECRET, algorithms=["HS256"])


def test_refresh_rotates_locked_active_session_atomically_and_persists_only_new_digest():
    raw_old = "old-refresh-token"
    old_session = _old_session(raw_old)
    session = FakeSession(old_session=old_session, user=_user())

    response = AuthService(session).refresh(RefreshTokenRequest(refresh_token=raw_old))

    replacement = session.added[0]
    assert response.refresh_token != raw_old
    assert replacement.token_hash != response.refresh_token
    assert verify_refresh_token(response.refresh_token, replacement.token_hash, secret=TEST_REFRESH_SECRET)
    assert replacement.user_id == old_session.user_id
    assert replacement.expires_at > datetime.now(timezone.utc)
    assert old_session.revoked_at is not None
    assert old_session.replaced_by_session_id == replacement.id
    assert session.commit_count == 1
    assert session.rollback_count == 0
    assert session.scalar_statement._for_update_arg is not None
    claims = _decode_access(response.access_token)
    assert claims["sub"] == str(old_session.user_id)
    assert claims["type"] == "access"
    assert {"email", "password_hash", "refresh_token"}.isdisjoint(claims)


@pytest.mark.parametrize("state", ["missing", "revoked", "expired", "missing_user", "inactive_user"])
def test_refresh_invalid_session_or_user_state_uses_generic_failure(state):
    raw_token = {
        "missing": "not-present",
        "revoked": "revoked-token",
        "expired": "expired-token",
        "missing_user": "missing-user-token",
        "inactive_user": "inactive-user-token",
    }[state]
    old_session = {
        "missing": None,
        "revoked": _old_session(raw_token, revoked=True),
        "expired": _old_session(raw_token, expired=True),
        "missing_user": _old_session(raw_token),
        "inactive_user": _old_session(raw_token),
    }[state]
    user = {"missing_user": None, "inactive_user": _user(active=False)}.get(state, _user())
    session = FakeSession(old_session=old_session, user=user)
    with pytest.raises(AuthenticationFailedException) as exc_info:
        AuthService(session).refresh(RefreshTokenRequest(refresh_token=raw_token))
    assert exc_info.value.code == "authentication_failed"
    assert exc_info.value.message == "Invalid email or password."
    assert session.commit_count == 0
    assert session.rollback_count == 1
    assert session.added == []


@pytest.mark.parametrize("fail_flush_at,fail_commit", [(1, False), (2, False), (None, True)])
def test_refresh_persistence_or_commit_failure_rolls_back_without_success(fail_flush_at, fail_commit):
    raw_old = "old-refresh-token"
    old_session = _old_session(raw_old)
    session = FakeSession(old_session=old_session, user=_user(), fail_flush_at=fail_flush_at, fail_commit=fail_commit)
    with pytest.raises(RuntimeError):
        AuthService(session).refresh(RefreshTokenRequest(refresh_token=raw_old))
    assert session.commit_count == (1 if fail_commit else 0)
    assert session.rollback_count == 1


def test_refresh_route_uses_only_refresh_token_input_and_generic_failure(monkeypatch):
    class FakeAuthService:
        def __init__(self, _session):
            pass

        def refresh(self, _request):
            raise AuthenticationFailedException()

    monkeypatch.setattr(auth_route, "AuthService", FakeAuthService)
    app.dependency_overrides[get_db] = lambda: FakeSession(old_session=None, user=None)
    try:
        with TestClient(app) as client:
            rejected = client.post("/api/v1/auth/refresh", json={"refresh_token": "raw", "user_id": str(_user().id)})
            invalid = client.post("/api/v1/auth/refresh", json={"refresh_token": "raw"})
        assert rejected.status_code == 422
        assert invalid.status_code == 401
        assert rejected.json()["error"] == {"code": "validation_error", "message": "The request payload is invalid."}
    finally:
        app.dependency_overrides.clear()
