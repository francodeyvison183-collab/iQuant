"""label_session / label_pair for historical labeling (iteration 1).

Revision ID: 0003_label_annotation
Revises: 0002_admin_identity
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_label_annotation"
down_revision = "0002_admin_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "label_session",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("admin_user_id", sa.Integer(), nullable=True),
        sa.Column("full_code", sa.String(length=24), nullable=False, index=True),
        sa.Column("period", sa.String(length=16), nullable=False, server_default="day"),
        sa.Column("title", sa.String(length=128), nullable=True),
        sa.Column(
            "idempotency_key",
            sa.String(length=128),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["admin_user_id"], ["admin_user.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("admin_user_id", "idempotency_key", name="uq_label_session_admin_idem"),
    )
    op.create_index("ix_label_session_admin_created", "label_session", ["admin_user_id", "created_at"])

    op.create_table(
        "label_pair",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("label_session.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("buy_bar_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sell_bar_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("buy_close", sa.Numeric(20, 6), nullable=False),
        sa.Column("sell_close", sa.Numeric(20, 6), nullable=False),
        sa.Column("return_pct", sa.Numeric(20, 10), nullable=False),
        sa.UniqueConstraint("session_id", "sort_order", name="uq_label_pair_session_order"),
    )


def downgrade() -> None:
    op.drop_table("label_pair")
    op.drop_table("label_session")
