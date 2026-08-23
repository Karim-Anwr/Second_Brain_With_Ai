"""Focused Phase 2.3C-1 tests using fake sessions; no live PostgreSQL is required."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth.current_user import CurrentUser
from app.auth.dependencies import get_current_user
from app.auth.tokens import AccessTokenVerificationError, create_access_token, verify_access_token
from app.core.config import settings
from app.core.exceptions import AuthenticationFailedException
from app.db.models.user import User
from app.db.session import get_db


TEST_JWT_SECRET = "test-jwt-signing-secret-with-at-least-thirty-two-characters"


@pytest.fixture(autouse=True)
def configured_jwt(monkeypatch):
    monkeypatch.setattr(settings, "jwt_signing_secret", TEST_JWT_SECRET)
    monkeypatch.setattr(settings, "jwt_algorithm", "HS256")
    monkeypatch.setattr(settings, "access_token_lifetime_seconds", 900)


class FakeSession:
    def __init__(self, user: User | None):
        self.user = user
        self.get_calls = []
        self.commit_calls = 0

    def get(self, model, user_id):
        self.get_calls.append((model, user_id))
        return self.user

    def commit(self):
        self.commit_calls += 1


def _user(*, is_active: bool = True) -> User:
    return User(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        email="person@example.com",
        password_hash="$argon2id$test-only-hash",
        display_name="Person",
        is_active=is_active,
    )


def _signed_token(claims: dict, *, secret: str = TEST_JWT_SECRET, algorithm: str = "HS256") -> str:
    return jwt.encode(claims, secret, algorithm=algorithm)


def _access_claims(user_id: UUID, **overrides) -> dict:
    now = datetime.now(timezone.utc)
    claims = {"sub": str(user_id), "type": "access", "iat": now, "exp": now + timedelta(minutes=5)}
    claims.update(overrides)
    return claims


def _dependency_app(session: FakeSession) -> FastAPI:
    test_app = FastAPI()

    @test_app.exception_handler(AuthenticationFailedException)
    async def auth_failure_handler(_request, exc):
        return __import__("fastapi").responses.JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @test_app.get("/probe")
    def probe(current_user: CurrentUser = Depends(get_current_user)):
        return {"id": str(current_user.id)}

    test_app.dependency_overrides[get_db] = lambda: session
    return test_app


def test_verify_access_token_returns_uuid_only_after_signature_and_claim_validation():
    user_id = uuid4()
    token = create_access_token(user_id).value
    assert verify_access_token(token) == user_id


@pytest.mark.parametrize(
    "claims,secret",
    [
        ({}, TEST_JWT_SECRET),
        (_access_claims(uuid4(), exp=datetime.now(timezone.utc) - timedelta(seconds=1)), TEST_JWT_SECRET),
        (_access_claims(uuid4(), sub="not-a-uuid"), TEST_JWT_SECRET),
        (_access_claims(uuid4(), type="refresh"), TEST_JWT_SECRET),
        (_access_claims(uuid4()), "different-signing-secret-with-at-least-32-chars"),
    ],
)
def test_verify_access_token_rejects_invalid_signature_expiration_and_required_claims(claims, secret):
    with pytest.raises(AccessTokenVerificationError):
        verify_access_token(_signed_token(claims, secret=secret))


@pytest.mark.parametrize("token", ["not-a-jwt", "", "abc.def.ghi"])
def test_verify_access_token_rejects_malformed_tokens(token):
    with pytest.raises(AccessTokenVerificationError):
        verify_access_token(token)


def test_current_user_dependency_returns_active_database_user_and_never_commits():
    user = _user()
    session = FakeSession(user)
    token = create_access_token(user.id).value
    app = _dependency_app(session)

    with TestClient(app) as client:
        response = client.get("/probe", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {"id": str(user.id)}
    assert session.get_calls == [(User, user.id)]
    assert session.commit_calls == 0


@pytest.mark.parametrize("authorization", [None, "Basic token", "Bearer", "Bearer not-a-jwt"])
def test_current_user_dependency_rejects_missing_wrong_and_malformed_authorization(authorization):
    app = _dependency_app(FakeSession(_user()))
    headers = {} if authorization is None else {"Authorization": authorization}
    with TestClient(app) as client:
        response = client.get("/probe", headers=headers)
    assert response.status_code == 401
    assert response.json() == {"error": {"code": "authentication_failed", "message": "Invalid email or password."}}


@pytest.mark.parametrize("user", [None, _user(is_active=False)])
def test_current_user_dependency_rejects_missing_and_inactive_users_with_generic_failure(user):
    token = create_access_token(_user().id).value
    app = _dependency_app(FakeSession(user))
    with TestClient(app) as client:
        response = client.get("/probe", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["error"] == {"code": "authentication_failed", "message": "Invalid email or password."}


def test_client_supplied_query_user_id_cannot_override_verified_token_subject():
    user = _user()
    token = create_access_token(user.id).value
    app = _dependency_app(FakeSession(user))
    with TestClient(app) as client:
        response = client.get("/probe?user_id={uuid4()}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["id"] == str(user.id)
