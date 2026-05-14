"""init business schema

业务主库初始迁移：symbol, tdx_host, market_import_task, market_import_state。

Revision ID: 0001_init_business
Revises:
Create Date: 2026-05-14 00:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_init_business"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "symbol",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=16), nullable=False, index=True),
        sa.Column("market", sa.String(length=4), nullable=False, index=True),
        sa.Column("full_code", sa.String(length=20), nullable=False, unique=True, index=True),
        sa.Column("name", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("asset_type", sa.String(length=16), nullable=False, server_default="stock"),
        sa.Column("list_date", sa.Date(), nullable=True),
        sa.Column("delist_date", sa.Date(), nullable=True),
        sa.Column("extra", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("market", "code", name="uq_symbol_market_code"),
    )

    op.create_table(
        "tdx_host",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ip", sa.String(length=64), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="untested"),
        sa.Column("speed_ms", sa.Integer(), nullable=False, server_default="9999"),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("last_tested", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fail_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("ip", "port", name="uq_tdx_host_addr"),
    )

    op.create_table(
        "market_import_task",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.String(length=40), nullable=False, unique=True, index=True),
        sa.Column("task_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued", index=True),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("total_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("done_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("imported_bars", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.String(length=2048), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_market_import_task_created_at",
        "market_import_task",
        ["created_at"],
        postgresql_using="btree",
    )

    op.create_table(
        "market_import_state",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("file_path", sa.String(length=512), nullable=False, index=True),
        sa.Column("full_code", sa.String(length=20), nullable=False, index=True),
        sa.Column("period", sa.String(length=8), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("file_mtime", sa.Float(), nullable=False, server_default="0"),
        sa.Column("imported_records", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("last_bar_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_task_id",
            sa.String(length=40),
            sa.ForeignKey("market_import_task.task_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("file_path", name="uq_market_import_state_file"),
    )


def downgrade() -> None:
    op.drop_table("market_import_state")
    op.drop_index("ix_market_import_task_created_at", table_name="market_import_task")
    op.drop_table("market_import_task")
    op.drop_table("tdx_host")
    op.drop_table("symbol")
