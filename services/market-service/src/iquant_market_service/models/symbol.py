"""标的基础信息表。"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base import PgBase


class SymbolORM(PgBase):
    __tablename__ = "symbol"
    __table_args__ = (UniqueConstraint("market", "code", name="uq_symbol_market_code"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    market: Mapped[str] = mapped_column(String(4), index=True, nullable=False)
    full_code: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    asset_type: Mapped[str] = mapped_column(String(16), nullable=False, default="stock")
    list_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    delist_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    extra: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
