"""行情导入任务与导入状态。"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base import PgBase


class MarketImportTaskType(StrEnum):
    INCREMENTAL = "incremental"
    FULL = "full"
    ONLINE_FETCH = "online_fetch"  # 单标的在线补数
    ONLINE_BATCH = "online_batch"  # 按市场/日期范围/周期批量在线更新


class MarketImportTaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MarketImportTask(PgBase):
    """行情导入任务。"""

    __tablename__ = "market_import_task"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    task_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued", index=True)
    params: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    total_files: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    done_files: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    imported_bars: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class MarketImportState(PgBase):
    """单个 TDX 文件最近一次导入状态，用于增量判断与续传。"""

    __tablename__ = "market_import_state"
    __table_args__ = (UniqueConstraint("file_path", name="uq_market_import_state_file"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    full_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(8), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    file_mtime: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    imported_records: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    last_bar_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_task_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey("market_import_task.task_id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
