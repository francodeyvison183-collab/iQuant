"""blind_session / blind_action / blind_consistency_report (scheme A, iteration 1a).

Revision ID: 0006_blind_replay
Revises: 0005_label_batch_summary
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006_blind_replay"
down_revision = "0005_label_batch_summary"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "blind_session",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("admin_user_id", sa.Integer(), nullable=True),
        sa.Column("full_code", sa.String(length=24), nullable=False),
        sa.Column("period", sa.String(length=16), nullable=False, server_default="day"),
        sa.Column("range_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("range_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "cursor_bar_time",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="当前已暴露的最后一根 K 线时间（含）",
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="active",
            comment="active | paused | finished | abandoned",
        ),
        sa.Column(
            "strategy_version_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="对照已确认 DSL 时填写；归纳阶段为空",
        ),
        sa.Column(
            "source",
            sa.String(length=32),
            nullable=False,
            server_default="blind_replay",
        ),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column(
            "cash_balance",
            sa.Numeric(20, 4),
            nullable=False,
            server_default="1000000",
        ),
        sa.Column(
            "position_qty",
            sa.Numeric(20, 6),
            nullable=False,
            server_default="0",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["admin_user_id"], ["admin_user.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_blind_session_admin_created", "blind_session", ["admin_user_id", "created_at"])
    op.create_index("ix_blind_session_admin_status", "blind_session", ["admin_user_id", "status"])
    op.create_unique_constraint(
        "uq_blind_session_admin_idem",
        "blind_session",
        ["admin_user_id", "idempotency_key"],
    )

    op.create_table(
        "blind_action",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("blind_session.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("bar_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "user_action",
            sa.String(length=16),
            nullable=False,
            comment="buy | sell | hold",
        ),
        sa.Column("features_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "strategy_signal",
            sa.String(length=16),
            nullable=True,
            comment="buy | sell | hold | null，对照 DSL 阶段使用",
        ),
        sa.Column("user_reasons", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("confidence", sa.String(length=16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_blind_action_session_bar", "blind_action", ["session_id", "bar_time"])

    op.create_table(
        "blind_consistency_report",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("admin_user_id", sa.Integer(), nullable=True),
        sa.Column("period", sa.String(length=16), nullable=False, server_default="day"),
        sa.Column("session_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("scores_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("profile_draft", sa.Text(), nullable=False, server_default=""),
        sa.Column("insights_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("correction_options_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("user_corrections_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "ready_for_strategy",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["admin_user_id"], ["admin_user.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_blind_consistency_admin_created",
        "blind_consistency_report",
        ["admin_user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("blind_consistency_report")
    op.drop_table("blind_action")
    op.drop_table("blind_session")
