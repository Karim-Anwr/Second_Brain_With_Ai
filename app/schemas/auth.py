"""Public authentication API contracts; plaintext passwords never cross persistence DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.db.email import canonicalize_email


class RegistrationRequest(BaseModel):
    email: str
    password: str = Field(min_length=1)
    display_name: str | None = Field(default=None, max_length=120)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return canonicalize_email(value)

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("display_name must not be blank")
        return value


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=1)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return canonicalize_email(value)


class AuthTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    expires_in: int
