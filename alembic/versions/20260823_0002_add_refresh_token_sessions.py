"""Add digest-only refresh token sessions for Phase 2.3A.

Revision ID: 20260823_0002
Revises: 20260822_0001
Create Date: 2026-08-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260823_0002"
down_revision = "20260822_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "refresh_token_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint("token_hash ~ '^[0-9a-f]{64}$'", name="ck_refresh_token_sessions_token_hash"),
        sa.CheckConstraint(
            "expires_at > created_at", name="ck_refresh_token_sessions_expiry_after_created"
        ),
        sa.CheckConstraint(
            "replaced_by_session_id IS NULL OR replaced_by_session_id <> id",
            name="ck_refresh_token_sessions_no_self_replacement",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_refresh_token_sessions_user_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["replaced_by_session_id"],
            ["refresh_token_sessions.id"],
            name="fk_refresh_token_sessions_replaced_by_session_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_refresh_token_sessions_token_hash"),
        sa.UniqueConstraint("replaced_by_session_id", name="uq_refresh_token_sessions_replacement"),
    )
    op.create_index("ix_refresh_token_sessions_user_id", "refresh_token_sessions", ["user_id"], unique=False)
    op.create_index(
        "ix_refresh_token_sessions_expires_at", "refresh_token_sessions", ["expires_at"], unique=False
    )
    op.create_index(
        "ix_refresh_token_sessions_revoked_at", "refresh_token_sessions", ["revoked_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_refresh_token_sessions_revoked_at", table_name="refresh_token_sessions")
    op.drop_index("ix_refresh_token_sessions_expires_at", table_name="refresh_token_sessions")
    op.drop_index("ix_refresh_token_sessions_user_id", table_name="refresh_token_sessions")
    op.drop_table("refresh_token_sessions")
