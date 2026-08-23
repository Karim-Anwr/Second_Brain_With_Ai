"""Authoritative PostgreSQL ownership records for new logical business resources."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.db.base import Base


class OwnedResourceKind(str, Enum):
    """Logical resource types supported by the initial ownership authority."""

    MEMORY = "memory"
    FILE = "file"
    CHAT_SESSION = "chat_session"


class OwnedResource(Base):
    """Immutable owner mapping for a logical resource persisted outside PostgreSQL."""

    __tablename__ = "owned_resources"
    __table_args__ = (
        UniqueConstraint("resource_kind", "resource_id", name="uq_owned_resources_kind_resource_id"),
        CheckConstraint(
            "resource_kind IN ('memory', 'file', 'chat_session')",
            name="ck_owned_resources_resource_kind",
        ),
        CheckConstraint(
            "resource_id = btrim(resource_id) AND btrim(resource_id) <> ''",
            name="ck_owned_resources_resource_id_canonical_nonblank",
        ),
        Index("ix_owned_resources_owner_user_id", "owner_user_id"),
        Index("ix_owned_resources_owner_user_id_resource_kind", "owner_user_id", "resource_kind"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    resource_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(128), nullable=False)
    owner_user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", name="fk_owned_resources_owner_user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    @validates("resource_kind")
    def validate_resource_kind(self, _key: str, value: OwnedResourceKind | str) -> str:
        normalized = value.value if isinstance(value, OwnedResourceKind) else str(value)
        if normalized not in {kind.value for kind in OwnedResourceKind}:
            raise ValueError("resource_kind is not supported")
        return normalized

    @validates("resource_id")
    def validate_resource_id(self, _key: str, value: str) -> str:
        if not isinstance(value, str) or not value or not value.strip():
            raise ValueError("resource_id must not be blank")
        if value != value.strip():
            raise ValueError("resource_id must be canonical without surrounding whitespace")
        if len(value) > 128:
            raise ValueError("resource_id must not exceed 128 characters")
        return value

    @validates("owner_user_id")
    def validate_immutable_owner(self, _key: str, value: UUID) -> UUID:
        existing_owner = getattr(self, "owner_user_id", None)
        if existing_owner is not None and value != existing_owner:
            raise ValueError("owner_user_id is immutable")
        return value
