"""Refresh-token session persistence without raw token storage or auth workflows."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.auth.refresh_tokens import is_refresh_token_hash
from app.db.base import Base


class RefreshTokenSession(Base):
    """A persisted, revocable refresh-token session keyed only by a digest."""

    __tablename__ = "refresh_token_sessions"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_refresh_token_sessions_token_hash"),
        UniqueConstraint("replaced_by_session_id", name="uq_refresh_token_sessions_replacement"),
        CheckConstraint("token_hash ~ '^[0-9a-f]{64}$'", name="ck_refresh_token_sessions_token_hash"),
        CheckConstraint("expires_at > created_at", name="ck_refresh_token_sessions_expiry_after_created"),
        CheckConstraint(
            "replaced_by_session_id IS NULL OR replaced_by_session_id <> id",
            name="ck_refresh_token_sessions_no_self_replacement",
        ),
        Index("ix_refresh_token_sessions_user_id", "user_id"),
        Index("ix_refresh_token_sessions_expires_at", "expires_at"),
        Index("ix_refresh_token_sessions_revoked_at", "revoked_at"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", name="fk_refresh_token_sessions_user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by_session_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "refresh_token_sessions.id",
            name="fk_refresh_token_sessions_replaced_by_session_id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    @validates("token_hash")
    def validate_token_hash(self, _key: str, value: str) -> str:
        if not is_refresh_token_hash(value):
            raise ValueError("token_hash must be a lowercase SHA-256 hex digest")
        return value
