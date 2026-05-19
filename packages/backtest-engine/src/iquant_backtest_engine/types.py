"""回测输入/输出类型。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class OhlcBar:
    bar_time: datetime
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class TradeRecord:
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    return_pct: float


@dataclass(frozen=True)
class BacktestRunResult:
    summary: dict[str, object]
    equity_curve: list[dict[str, object]]
    trades: list[TradeRecord]
    data_window: dict[str, object]
    warnings: list[str]
