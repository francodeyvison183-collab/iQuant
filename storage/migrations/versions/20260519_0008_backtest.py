"""backtest_task / backtest_report (iteration V0.2b).

Revision ID: 0008_backtest
Revises: 0007_behavior_strategy
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008_backtest"
down_revision = "0007_behavior_strategy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "backtest_task",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("admin_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "strategy_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("behavior_strategy_version.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("full_code", sa.String(length=24), nullable=False),
        sa.Column("period", sa.String(length=16), nullable=False, server_default="day"),
        sa.Column("params_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="queued",
            comment="queued | running | succeeded | failed",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("celery_task_id", sa.String(length=64), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["admin_user_id"], ["admin_user.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_backtest_task_admin_created", "backtest_task", ["admin_user_id", "created_at"])
    op.create_unique_constraint(
        "uq_backtest_task_admin_idem",
        "backtest_task",
        ["admin_user_id", "idempotency_key"],
    )

    op.create_table(
        "backtest_report",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("backtest_task.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("data_window_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("warnings_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("equity_curve_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("backtest_report")
    op.drop_table("backtest_task")
