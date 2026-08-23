"""One-way refresh-token digest helpers; opaque raw tokens are never persisted."""

from __future__ import annotations

import hashlib
import hmac
import re


_TOKEN_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_MIN_HASH_SECRET_LENGTH = 32


def _hash_secret(secret: str | None) -> bytes:
    if secret is None:
        from app.core.config import settings

        configured_secret = settings.refresh_token_hash_secret
    else:
        configured_secret = secret
    if not isinstance(configured_secret, str) or len(configured_secret) < _MIN_HASH_SECRET_LENGTH:
        raise ValueError(
            "REFRESH_TOKEN_HASH_SECRET must be at least 32 characters before hashing refresh tokens"
        )
    return configured_secret.encode("utf-8")


def hash_refresh_token(token: str, *, secret: str | None = None) -> str:
    """Return a keyed SHA-256 digest for an opaque refresh token."""
    if not isinstance(token, str) or not token:
        raise ValueError("refresh token must be a non-empty string")
    return hmac.new(_hash_secret(secret), token.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_refresh_token(token: str, token_hash: str, *, secret: str | None = None) -> bool:
    """Compare a raw refresh token to its stored digest without timing leaks."""
    if not isinstance(token_hash, str) or not _TOKEN_HASH_PATTERN.fullmatch(token_hash):
        return False
    try:
        expected_hash = hash_refresh_token(token, secret=secret)
    except ValueError:
        return False
    return hmac.compare_digest(expected_hash, token_hash)


def is_refresh_token_hash(value: str) -> bool:
    """Return whether a stored value has the canonical keyed SHA-256 digest shape."""
    return isinstance(value, str) and _TOKEN_HASH_PATTERN.fullmatch(value) is not None
