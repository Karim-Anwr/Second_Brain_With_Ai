"""Small signed opaque cursor helpers for public API presentation pagination."""

import base64
import binascii
import hashlib
import hmac
import json
from typing import Any

from app.core.config import settings
from app.core.exceptions import InvalidRequestException


def encode_cursor(kind: str, position: list[str]) -> str:
    """Encode a non-sensitive sort position without including owner or path data."""
    payload = json.dumps({"v": 1, "k": kind, "p": position}, separators=(",", ":"), sort_keys=True).encode()
    signature = hmac.new(_cursor_secret(), payload, hashlib.sha256).digest()
    return f"{_b64(payload)}.{_b64(signature)}"


def decode_cursor(cursor: str | None, kind: str) -> list[str] | None:
    """Validate and decode a cursor for one explicitly named collection."""
    if cursor is None:
        return None
    try:
        encoded_payload, encoded_signature = cursor.split(".", 1)
        payload = _unb64(encoded_payload)
        signature = _unb64(encoded_signature)
        expected = hmac.new(_cursor_secret(), payload, hashlib.sha256).digest()
        decoded: Any = json.loads(payload)
        if not hmac.compare_digest(signature, expected):
            raise ValueError("invalid signature")
        if decoded.get("v") != 1 or decoded.get("k") != kind:
            raise ValueError("invalid cursor kind")
        position = decoded.get("p")
        if not isinstance(position, list) or not all(isinstance(value, str) for value in position):
            raise ValueError("invalid position")
        return position
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError, binascii.Error):
        raise InvalidRequestException("The pagination cursor is invalid.") from None


def _cursor_secret() -> bytes:
    secret = settings.jwt_signing_secret
    if not isinstance(secret, str) or not secret:
        raise InvalidRequestException("Pagination is unavailable because server configuration is invalid.")
    return secret.encode()


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
