"""Add minimal logical-resource ownership authority for future owner-scoped operations.

Revision ID: 20260823_0003
Revises: 20260823_0002
Create Date: 2026-08-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260823_0003"
down_revision = "20260823_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "owned_resources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resource_kind", sa.String(length=32), nullable=False),
        sa.Column("resource_id", sa.String(length=128), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "resource_kind IN ('memory', 'file', 'chat_session')",
            name="ck_owned_resources_resource_kind",
        ),
        sa.CheckConstraint(
            "resource_id = btrim(resource_id) AND btrim(resource_id) <> ''",
            name="ck_owned_resources_resource_id_canonical_nonblank",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"], ["users.id"], name="fk_owned_resources_owner_user_id", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("resource_kind", "resource_id", name="uq_owned_resources_kind_resource_id"),
    )
    op.create_index("ix_owned_resources_owner_user_id", "owned_resources", ["owner_user_id"], unique=False)
    op.create_index(
        "ix_owned_resources_owner_user_id_resource_kind",
        "owned_resources",
        ["owner_user_id", "resource_kind"],
        unique=False,
    )
    op.execute(
        """
        CREATE FUNCTION prevent_owned_resource_owner_reassignment()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.owner_user_id IS DISTINCT FROM OLD.owner_user_id THEN
                RAISE EXCEPTION 'owned_resources.owner_user_id is immutable'
                    USING ERRCODE = 'integrity_constraint_violation';
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_owned_resources_owner_user_id_immutable
        BEFORE UPDATE OF owner_user_id ON owned_resources
        FOR EACH ROW
        EXECUTE FUNCTION prevent_owned_resource_owner_reassignment();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_owned_resources_owner_user_id_immutable ON owned_resources")
    op.execute("DROP FUNCTION IF EXISTS prevent_owned_resource_owner_reassignment()")
    op.drop_index("ix_owned_resources_owner_user_id_resource_kind", table_name="owned_resources")
    op.drop_index("ix_owned_resources_owner_user_id", table_name="owned_resources")
    op.drop_table("owned_resources")
