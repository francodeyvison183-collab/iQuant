"""blind_session.cursor_period for cross-period time alignment.

Revision ID: 0010_blind_cursor_period
Revises: 0009_blind_action_period
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010_blind_cursor_period"
down_revision = "0009_blind_action_period"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "blind_session",
        sa.Column(
            "cursor_period",
            sa.String(length=16),
            nullable=False,
            server_default="day",
        ),
    )
    op.execute("UPDATE blind_session SET cursor_period = period")
    op.alter_column("blind_session", "cursor_period", server_default=None)


def downgrade() -> None:
    op.drop_column("blind_session", "cursor_period")
