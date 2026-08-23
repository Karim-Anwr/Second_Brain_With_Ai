"""Canonical email handling shared by User persistence components."""

from __future__ import annotations

import re


_EMAIL_PATTERN = re.compile(
    r"^(?=.{1,320}$)[^@\s]+@(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$"
)


def canonicalize_email(value: str) -> str:
    """Trim, lowercase, and minimally validate an email before persistence or lookup."""
    if not isinstance(value, str):
        raise ValueError("email must be a string")

    email = value.strip().lower()
    if not email:
        raise ValueError("email must not be blank")
    if not _EMAIL_PATTERN.fullmatch(email):
        raise ValueError("email must be a valid address")
    return email
