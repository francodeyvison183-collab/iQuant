"""label_batch_summary for batch profile (iteration 1b).

Revision ID: 0005_label_batch_summary
Revises: 0004_label_batch
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_label_batch_summary"
down_revision = "0004_label_batch"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "label_batch_summary",
        sa.Column(
            "batch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("label_batch.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("stats_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("profile_draft", sa.Text(), nullable=False, server_default=""),
        sa.Column("insights_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("correction_options_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("user_corrections_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("label_batch_summary")
