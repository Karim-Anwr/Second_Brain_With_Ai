"""Persistence DTOs for the Phase 2.2 User model only."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.db.email import canonicalize_email


class UserCreate(BaseModel):
    """Validated persistence input; password_hash is never a plaintext password."""

    email: str
    password_hash: str
    display_name: str
    is_active: bool = True

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return canonicalize_email(value)

    @field_validator("password_hash", "display_name")
    @classmethod
    def require_nonblank_value(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value


class UserRecord(BaseModel):
    """Safe persistence projection that intentionally excludes password_hash."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    display_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
