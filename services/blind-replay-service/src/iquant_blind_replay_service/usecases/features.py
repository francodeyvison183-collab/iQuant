"""可见窗口特征快照（供模式归纳，非买卖信号）。"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from iquant_market_service.usecases.schemas import BarPoint


def _ma(values: list[Decimal], window: int) -> Decimal | None:
    if len(values) < window:
        return None
    chunk = values[-window:]
    return sum(chunk) / Decimal(window)


def build_features_snapshot(bars: list[BarPoint], *, cursor_idx: int) -> dict[str, Any]:
    """基于 cursor 及以前 K 线计算特征。"""
    if cursor_idx < 0 or cursor_idx >= len(bars):
        return {"error": "invalid_cursor"}
    window = bars[: cursor_idx + 1]
    closes = [b.close for b in window]
    vols = [Decimal(b.volume) for b in window]
    close = closes[-1]
    ma20 = _ma(closes, 20)
    ma20_dist: float | None = None
    if ma20 is not None and ma20 > 0:
        ma20_dist = float((close - ma20) / ma20)

    vol_avg = _ma(vols, 20)
    volume_ratio: float | None = None
    if vol_avg is not None and vol_avg > 0:
        volume_ratio = float(vols[-1] / vol_avg)

    return {
        "bar_time": window[-1].bar_time.isoformat(),
        "close": str(close),
        "ma20": str(ma20) if ma20 is not None else None,
        "ma20_dist": ma20_dist,
        "volume_ratio": volume_ratio,
        "bars_visible": len(window),
    }
