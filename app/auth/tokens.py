"""Minimal access-token and opaque refresh-token issuance for Phase 2.3B."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt

from app.core.config import settings


_MIN_SECRET_LENGTH = 32
_SUPPORTED_JWT_ALGORITHM = "HS256"


@dataclass(frozen=True)
class AccessToken:
    value: str
    expires_at: datetime


def _validate_jwt_configuration() -> tuple[str, str, int]:
    if not isinstance(settings.jwt_signing_secret, str) or len(settings.jwt_signing_secret) < _MIN_SECRET_LENGTH:
        raise ValueError("JWT_SIGNING_SECRET must be at least 32 characters before issuing access tokens")
    if settings.jwt_algorithm != _SUPPORTED_JWT_ALGORITHM:
        raise ValueError("JWT_ALGORITHM must be HS256")
    if not isinstance(settings.access_token_lifetime_seconds, int) or not 60 <= settings.access_token_lifetime_seconds <= 3600:
        raise ValueError("ACCESS_TOKEN_LIFETIME_SECONDS must be between 60 and 3600")
    return settings.jwt_signing_secret, settings.jwt_algorithm, settings.access_token_lifetime_seconds


def refresh_token_lifetime() -> timedelta:
    """Return the configured initial refresh-session lifetime after validation."""
    if not isinstance(settings.refresh_token_lifetime_seconds, int) or settings.refresh_token_lifetime_seconds <= 0:
        raise ValueError("REFRESH_TOKEN_LIFETIME_SECONDS must be positive")
    return timedelta(seconds=settings.refresh_token_lifetime_seconds)


def create_access_token(user_id: UUID) -> AccessToken:
    """Create a short-lived, signed access token containing no sensitive claims."""
    secret, algorithm, lifetime_seconds = _validate_jwt_configuration()
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(seconds=lifetime_seconds)
    value = jwt.encode(
        {"sub": str(user_id), "type": "access", "iat": issued_at, "exp": expires_at},
        secret,
        algorithm=algorithm,
    )
    return AccessToken(value=value, expires_at=expires_at)


def generate_refresh_token() -> str:
    """Generate a cryptographically strong opaque token for one-time client return."""
    return secrets.token_urlsafe(48)
