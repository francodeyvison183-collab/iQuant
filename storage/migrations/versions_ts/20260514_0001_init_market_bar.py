"""init market_bar hypertable

时序行情库初始迁移：market_bar 表 + TimescaleDB hypertable + 压缩策略。

Revision ID: ts_0001_market_bar
Revises:
Create Date: 2026-05-14 00:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "ts_0001_market_bar"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 启用 TimescaleDB 扩展（IF NOT EXISTS 保证幂等）
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")

    op.create_table(
        "market_bar",
        sa.Column("full_code", sa.String(length=20), nullable=False),
        sa.Column("period", sa.String(length=8), nullable=False),
        sa.Column("bar_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(18, 4), nullable=False),
        sa.Column("high", sa.Numeric(18, 4), nullable=False),
        sa.Column("low", sa.Numeric(18, 4), nullable=False),
        sa.Column("close", sa.Numeric(18, 4), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("adj_factor", sa.Numeric(18, 6), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="tdx-file"),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("full_code", "period", "bar_time", name="pk_market_bar"),
    )

    # 转 hypertable：按 bar_time 分区，每 7 天一个 chunk（日线偏稀疏，分钟线偏密集，整体折中）
    op.execute(
        "SELECT create_hypertable('market_bar', 'bar_time', "
        "chunk_time_interval => INTERVAL '7 days', if_not_exists => TRUE)"
    )

    # 常用查询索引：按 symbol+period 走时间倒序
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_market_bar_full_code_period_time "
        "ON market_bar (full_code, period, bar_time DESC)"
    )

    # 压缩策略：分段列为 full_code+period，按时间升序排列；30 天以上自动压缩
    op.execute(
        "ALTER TABLE market_bar SET ("
        "timescaledb.compress, "
        "timescaledb.compress_segmentby = 'full_code,period', "
        "timescaledb.compress_orderby = 'bar_time ASC'"
        ")"
    )
    op.execute(
        "SELECT add_compression_policy('market_bar', INTERVAL '30 days', if_not_exists => TRUE)"
    )


def downgrade() -> None:
    op.execute("SELECT remove_compression_policy('market_bar', if_exists => TRUE)")
    op.execute("DROP INDEX IF EXISTS ix_market_bar_full_code_period_time")
    op.drop_table("market_bar")
