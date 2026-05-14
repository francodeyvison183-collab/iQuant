"""市场 K 线表（TimescaleDB hypertable）。

注意：TimescaleDB 要求 hypertable 主键必须包含分区列 ``bar_time``，
否则无法 create_hypertable。
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Numeric, PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import TsBase


class MarketBarORM(TsBase):
    __tablename__ = "market_bar"
    __table_args__ = (
        PrimaryKeyConstraint("full_code", "period", "bar_time", name="pk_market_bar"),
    )

    full_code: Mapped[str] = mapped_column(String(20), nullable=False)
    period: Mapped[str] = mapped_column(String(8), nullable=False)
    bar_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    open: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, default=0)
    adj_factor: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="tdx-file")
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
