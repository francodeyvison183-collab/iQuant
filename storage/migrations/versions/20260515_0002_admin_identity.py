"""admin identity tables

Revision ID: 0002_admin_identity
Revises: 0001_init_business
Create Date: 2026-05-15
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_admin_identity"
down_revision = "0001_init_business"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_user",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=256), nullable=False),
        sa.Column("display_name", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("username", name="uq_admin_user_username"),
    )
    op.create_index("ix_admin_user_username", "admin_user", ["username"])

    op.create_table(
        "admin_refresh_token",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("admin_user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("user_agent", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["admin_user_id"], ["admin_user.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token_hash", name="uq_admin_refresh_token_hash"),
    )
    op.create_index("ix_admin_refresh_token_admin_user_id", "admin_refresh_token", ["admin_user_id"])

    op.create_table(
        "admin_audit_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("admin_user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("resource_id", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("method", sa.String(length=8), nullable=False, server_default=""),
        sa.Column("path", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("status_code", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ip", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("user_agent", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("request_id", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["admin_user_id"], ["admin_user.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_admin_audit_log_admin_user_id", "admin_audit_log", ["admin_user_id"])
    op.create_index("ix_admin_audit_log_action", "admin_audit_log", ["action"])
    op.create_index("ix_admin_audit_log_created_at", "admin_audit_log", ["created_at"])


def downgrade() -> None:
    op.drop_table("admin_audit_log")
    op.drop_table("admin_refresh_token")
    op.drop_table("admin_user")
