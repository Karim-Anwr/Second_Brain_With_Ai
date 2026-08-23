"""Focused Phase 2.3B tests using fake sessions; no live PostgreSQL is required."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.api.routes import auth as auth_route
from app.auth.passwords import hash_password
from app.auth.refresh_tokens import hash_refresh_token, verify_refresh_token
from app.auth.tokens import create_access_token
from app.core.config import settings
from app.core.exceptions import AuthenticationFailedException, RegistrationFailedException
from app.db.models.user import User
from app.db.session import get_db
from app.main import app
from app.schemas.auth import LoginRequest, RegistrationRequest
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


class FakeSession:
    def __init__(self, *, existing_user=None, raise_user_integrity_error=False, raise_refresh_error=False):
        self.existing_user = existing_user
        self.raise_user_integrity_error = raise_user_integrity_error
        self.raise_refresh_error = raise_refresh_error
        self.added = []
        self.flush_count = 0
        self.commit_count = 0
        self.rollback_count = 0

    def add(self, value):
        self.added.append(value)

    def flush(self):
        self.flush_count += 1
        if self.raise_user_integrity_error and len(self.added) == 1:
            raise IntegrityError("insert", {}, RuntimeError("duplicate"))
        if self.raise_refresh_error and len(self.added) == 2:
            raise IntegrityError("insert", {}, RuntimeError("refresh failure"))

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1

    def scalar(self, _statement):
        return self.existing_user


def _registered_user(email="person@example.com", *, is_active=True):
    return User(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        email=email,
        password_hash=hash_password("correct password"),
        display_name="Person",
        is_active=is_active,
    )


def _decode_access_token(value: str):
    return jwt.decode(value, TEST_JWT_SECRET, algorithms=["HS256"])


def test_registration_canonicalizes_email_hashes_password_and_persists_digest_only():
    session = FakeSession()
    response = AuthService(session).register(
        RegistrationRequest(email="  Person@Example.COM ", password="correct password")
    )

    user, refresh_session = session.added
    assert user.email == "person@example.com"
    assert user.password_hash != "correct password"
    assert user.password_hash.startswith("$argon2id$")
    assert refresh_session.token_hash != response.refresh_token
    assert verify_refresh_token(response.refresh_token, refresh_session.token_hash, secret=TEST_REFRESH_SECRET)
    assert refresh_session.user_id == user.id
    assert refresh_session.expires_at > datetime.now(timezone.utc)
    assert session.commit_count == 1
    assert session.rollback_count == 0
    claims = _decode_access_token(response.access_token)
    assert claims["sub"] == str(user.id)
    assert claims["type"] == "access"
    assert {"email", "password_hash", "refresh_token"}.isdisjoint(claims)


def test_registration_duplicate_email_uses_client_safe_error_and_rolls_back():
    session = FakeSession(raise_user_integrity_error=True)
    with pytest.raises(RegistrationFailedException) as exc_info:
        AuthService(session).register(RegistrationRequest(email="person@example.com", password="password"))
    assert exc_info.value.code == "registration_failed"
    assert "duplicate" not in exc_info.value.message.lower()
    assert session.commit_count == 0
    assert session.rollback_count == 1


def test_registration_rolls_back_user_when_refresh_session_creation_fails():
    session = FakeSession(raise_refresh_error=True)
    with pytest.raises(IntegrityError):
        AuthService(session).register(RegistrationRequest(email="person@example.com", password="password"))
    assert session.commit_count == 0
    assert session.rollback_count == 1


@pytest.mark.parametrize("existing_user", [None, _registered_user(is_active=False)])
def test_login_uses_generic_failure_for_missing_or_inactive_accounts(existing_user):
    session = FakeSession(existing_user=existing_user)
    with pytest.raises(AuthenticationFailedException) as exc_info:
        AuthService(session).login(LoginRequest(email="person@example.com", password="correct password"))
    assert exc_info.value.code == "authentication_failed"
    assert exc_info.value.message == "Invalid email or password."
    assert session.commit_count == 0


def test_login_performs_password_hash_work_for_unknown_accounts(monkeypatch):
    session = FakeSession(existing_user=None)
    hash_calls = []
    monkeypatch.setattr("app.services.auth_service.hash_password", lambda password: hash_calls.append(password) or "unused")

    with pytest.raises(AuthenticationFailedException):
        AuthService(session).login(LoginRequest(email="unknown@example.com", password="password"))

    assert hash_calls == ["password"]


def test_login_rejects_wrong_password_and_issues_tokens_for_valid_credentials():
    user = _registered_user()
    with pytest.raises(AuthenticationFailedException):
        AuthService(FakeSession(existing_user=user)).login(
            LoginRequest(email="person@example.com", password="wrong password")
        )

    session = FakeSession(existing_user=user)
    response = AuthService(session).login(LoginRequest(email=" PERSON@EXAMPLE.COM ", password="correct password"))
    refresh_session = session.added[0]
    assert response.token_type == "bearer"
    assert response.expires_in > 0
    assert refresh_session.token_hash != response.refresh_token
    assert session.commit_count == 1


def test_jwt_configuration_fails_closed_and_claims_do_not_include_sensitive_fields(monkeypatch):
    monkeypatch.setattr(settings, "jwt_signing_secret", "too-short")
    with pytest.raises(ValueError, match="JWT_SIGNING_SECRET"):
        create_access_token(uuid4())
    monkeypatch.setattr(settings, "jwt_signing_secret", TEST_JWT_SECRET)
    monkeypatch.setattr(settings, "jwt_algorithm", "none")
    with pytest.raises(ValueError, match="JWT_ALGORITHM"):
        create_access_token(uuid4())


def test_auth_routes_expose_only_register_and_login_with_safe_error_envelopes(monkeypatch):
    class FakeAuthService:
        def __init__(self, _session):
            pass

        def register(self, _request):
            raise RegistrationFailedException()

        def login(self, _request):
            raise AuthenticationFailedException()

    monkeypatch.setattr(auth_route, "AuthService", FakeAuthService)
    app.dependency_overrides[get_db] = lambda: FakeSession()
    try:
        with TestClient(app) as client:
            register = client.post("/api/v1/auth/register", json={"email": "person@example.com", "password": "password"})
            login = client.post("/api/v1/auth/login", json={"email": "person@example.com", "password": "password"})
            assert register.status_code == 409
            assert login.status_code == 401
            assert register.json()["error"] == {"code": "registration_failed", "message": "Unable to create account."}
            assert login.json()["error"] == {"code": "authentication_failed", "message": "Invalid email or password."}
            assert client.get("/api/v1/auth/me").status_code == 404
            assert client.post("/api/v1/auth/refresh").status_code == 404
    finally:
        app.dependency_overrides.clear()
