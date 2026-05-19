"""回测报告 ORM。"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import PgBase

if TYPE_CHECKING:
    from .backtest_task import BacktestTaskORM


class BacktestReportORM(PgBase):
    __tablename__ = "backtest_report"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("backtest_task.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    summary_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    data_window_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    warnings_json: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    equity_curve_json: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    task: Mapped["BacktestTaskORM"] = relationship("BacktestTaskORM", back_populates="report")
