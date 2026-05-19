"""blind_action.period for multi-timeframe trading.

Revision ID: 0009_blind_action_period
Revises: 0008_backtest
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_blind_action_period"
down_revision = "0008_backtest"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "blind_action",
        sa.Column(
            "period",
            sa.String(length=16),
            nullable=False,
            server_default="day",
        ),
    )
    # 历史数据回填为所属会话的 period
    op.execute(
        """
        UPDATE blind_action a
           SET period = s.period
          FROM blind_session s
         WHERE a.session_id = s.id
        """
    )
    op.alter_column("blind_action", "period", server_default=None)


def downgrade() -> None:
    op.drop_column("blind_action", "period")
