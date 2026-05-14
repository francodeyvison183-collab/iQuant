"""通达信主站持久化（与 host_manager 的 JSON 文件等价的数据库表，供后台编辑使用）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base import PgBase


class TdxHostORM(PgBase):
    __tablename__ = "tdx_host"
    __table_args__ = (UniqueConstraint("ip", "port", name="uq_tdx_host_addr"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ip: Mapped[str] = mapped_column(String(64), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="untested")
    speed_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=9999)
    is_builtin: Mapped[bool] = mapped_column(default=False, server_default="false", nullable=False)
    last_tested: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fail_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
