"""Pydantic schemas for persistence boundaries that are not HTTP routes."""

from app.schemas.user import UserCreate, UserRecord

__all__ = ["UserCreate", "UserRecord"]
