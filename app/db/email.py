"""Canonical email handling shared by User persistence components."""

from __future__ import annotations


def canonicalize_email(value: str) -> str:
    """Trim and lowercase an email address before persistence or lookup."""
    if not isinstance(value, str):
        raise ValueError("email must be a string")

    email = value.strip().lower()
    if not email:
        raise ValueError("email must not be blank")
    return email
