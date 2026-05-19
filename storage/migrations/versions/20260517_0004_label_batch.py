"""label_batch / label_queue_item for batch labeling (iteration 1a).

Revision ID: 0004_label_batch
Revises: 0003_label_annotation
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_label_batch"
down_revision = "0003_label_annotation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "label_batch",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("admin_user_id", sa.Integer(), nullable=True, index=True),
        sa.Column("period", sa.String(length=16), nullable=False, server_default="day"),
        sa.Column("market_filter", sa.String(length=16), nullable=True),
        sa.Column("batch_size", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["admin_user_id"], ["admin_user.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_label_batch_admin_created", "label_batch", ["admin_user_id", "created_at"])

    op.create_table(
        "label_queue_item",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "batch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("label_batch.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("full_code", sa.String(length=24), nullable=False),
        sa.Column("symbol_name", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("skip_reason", sa.String(length=64), nullable=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("label_session.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("batch_id", "sort_order", name="uq_label_queue_item_batch_order"),
    )
    op.create_index("ix_label_queue_item_batch_status", "label_queue_item", ["batch_id", "status"])


def downgrade() -> None:
    op.drop_table("label_queue_item")
    op.drop_table("label_batch")
