"""回测 API schema。"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BacktestCreateIn(BaseModel):
    model_config = ConfigDict(frozen=True)

    strategy_version_id: UUID
    full_code: str = Field(min_length=4, max_length=24)
    period: str | None = Field(default=None, max_length=16)
    initial_cash: str | None = Field(default=None, max_length=32)


class BacktestReportOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    summary: dict[str, Any]
    data_window: dict[str, Any]
    warnings: list[str]
    equity_curve: list[dict[str, Any]]
    created_at: datetime


class BacktestTaskOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    strategy_version_id: UUID
    full_code: str
    period: str
    status: str
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    report: BacktestReportOut | None


class BacktestTaskSummaryOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    strategy_version_id: UUID
    full_code: str
    period: str
    status: str
    strategy_name: str | None
    total_return: str | None
    created_at: datetime
    finished_at: datetime | None
