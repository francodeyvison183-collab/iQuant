"""盲测 API 用 Pydantic 模型。"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BlindSessionCreateIn(BaseModel):
    model_config = ConfigDict(frozen=True)

    full_code: str | None = Field(default=None, min_length=4, max_length=24)
    period: str = Field(default="day", max_length=16)
    months_back: int | None = Field(default=None, ge=1, le=24)
    market: str | None = Field(default=None, max_length=16)
    range_start: datetime | None = Field(default=None)
    range_end: datetime | None = Field(default=None)


class BlindActionIn(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_action: str = Field(pattern=r"^(buy|sell|hold)$")
    period: str | None = Field(default=None, max_length=16)
    user_reasons: list[str] | None = Field(default=None, max_length=8)
    confidence: str | None = Field(default=None, max_length=16)


class BarPointOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    bar_time: datetime
    open: str
    high: str
    low: str
    close: str
    volume: int
    amount: str


class BlindActionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    bar_time: datetime
    period: str
    user_action: str
    features_snapshot: dict[str, Any]
    strategy_signal: str | None
    user_reasons: list[str] | None
    confidence: str | None
    created_at: datetime


class BlindSessionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    display_label: str
    display_name: str | None
    full_code: str
    symbol_name: str | None
    period: str
    range_start: datetime
    range_end: datetime
    cursor_bar_time: datetime
    status: str
    source: str
    cash_balance: str
    position_qty: str
    action_count: int
    trade_action_count: int
    round_trade_count: int
    required_trade_actions: int
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class BlindSessionDetailOut(BlindSessionOut):
    model_config = ConfigDict(frozen=True)

    view_period: str
    visible_bars: list[BarPointOut]
    actions: list[BlindActionOut]
    can_act: bool


class BlindSessionSummaryOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    display_label: str
    display_name: str | None
    full_code: str
    symbol_name: str | None
    period: str
    status: str
    action_count: int
    trade_action_count: int
    created_at: datetime
    completed_at: datetime | None


class BlindRoundStockOut(BaseModel):
    """轮次中访问过的单只股票汇总。"""

    model_config = ConfigDict(frozen=True)

    session_id: UUID
    display_label: str
    display_name: str | None
    full_code: str
    symbol_name: str | None
    status: str
    trade_action_count: int
    created_at: datetime


class BlindRoundOut(BaseModel):
    """训练轮次（由若干 BlindSession 推导）。"""

    model_config = ConfigDict(frozen=True)

    round_id: UUID
    status: str
    period: str
    range_start: datetime
    range_end: datetime
    trade_action_count: int
    required_trade_actions: int
    stock_count: int
    started_at: datetime
    completed_at: datetime | None
    stocks: list[BlindRoundStockOut]


class BlindConsistencyReportOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    period: str
    session_count: int
    scores: dict[str, Any]
    profile_draft: str
    insights: list[str]
    correction_options: list[dict[str, str]]
    user_corrections: list[str]
    ready_for_strategy: bool
    created_at: datetime
    updated_at: datetime


class BlindConsistencyPatchIn(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_corrections: list[str] = Field(default_factory=list, max_length=8)
