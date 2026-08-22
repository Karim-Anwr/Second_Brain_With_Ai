"""PostgreSQL-backed User ORM model for Phase 2.2 persistence only."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.db.base import Base
from app.db.email import canonicalize_email


class User(Base):
    """A user record without authentication or authorization behavior."""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        CheckConstraint("email = lower(btrim(email))", name="ck_users_email_canonical"),
        CheckConstraint("char_length(btrim(email)) > 0", name="ck_users_email_not_blank"),
        CheckConstraint("char_length(btrim(password_hash)) > 0", name="ck_users_password_hash_not_blank"),
        CheckConstraint("char_length(btrim(display_name)) > 0", name="ck_users_display_name_not_blank"),
        Index("ix_users_is_active", "is_active"),
        Index("ix_users_created_at", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    @validates("email")
    def normalize_email(self, _key: str, value: str) -> str:
        return canonicalize_email(value)
