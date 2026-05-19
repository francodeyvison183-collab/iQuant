"""behavior_strategy / behavior_strategy_version (iteration V0.2a).

Revision ID: 0007_behavior_strategy
Revises: 0006_blind_replay
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_behavior_strategy"
down_revision = "0006_blind_replay"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "behavior_strategy",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("admin_user_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="draft",
            comment="draft | confirmed | archived",
        ),
        sa.Column(
            "source",
            sa.String(length=32),
            nullable=False,
            server_default="blind_replay",
        ),
        sa.Column(
            "consistency_report_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("period", sa.String(length=16), nullable=False, server_default="day"),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["admin_user_id"], ["admin_user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["consistency_report_id"],
            ["blind_consistency_report.id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_behavior_strategy_admin_created", "behavior_strategy", ["admin_user_id", "created_at"])
    op.create_unique_constraint(
        "uq_behavior_strategy_admin_idem",
        "behavior_strategy",
        ["admin_user_id", "idempotency_key"],
    )

    op.create_table(
        "behavior_strategy_version",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "strategy_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("behavior_strategy.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="draft",
            comment="draft | confirmed",
        ),
        sa.Column("dsl_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rules_summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rank_score", sa.Numeric(6, 4), nullable=False, server_default="0"),
        sa.Column("is_selected", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_behavior_strategy_version_strategy",
        "behavior_strategy_version",
        ["strategy_id", "version_no"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("behavior_strategy_version")
    op.drop_table("behavior_strategy")
