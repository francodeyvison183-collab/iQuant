"""pytdx 原始记录 → ``iquant_domain`` 模型。"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from iquant_domain.market import KlinePeriod, MarketBar


def parse_pytdx_datetime(val: object) -> datetime | None:
    """解析 ``get_security_bars`` 返回的 ``datetime`` 字段。"""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    s = str(val).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def bars_from_pytdx(
    raw: list[dict[str, Any]] | None,
    *,
    full_code: str,
    period: KlinePeriod,
) -> list[MarketBar]:
    """将 pytdx ``get_security_bars`` 结果转为 ``MarketBar`` 列表（时间升序）。"""
    if not raw:
        return []
    bars: list[MarketBar] = []
    for row in raw:
        bar_time = parse_pytdx_datetime(row.get("datetime"))
        if bar_time is None:
            continue
        try:
            bars.append(
                MarketBar(
                    full_code=full_code,
                    period=period,
                    bar_time=bar_time,
                    open=Decimal(str(row.get("open", 0) or 0)),
                    high=Decimal(str(row.get("high", 0) or 0)),
                    low=Decimal(str(row.get("low", 0) or 0)),
                    close=Decimal(str(row.get("close", 0) or 0)),
                    volume=int(row.get("vol", 0) or 0),
                    amount=Decimal(str(round(float(row.get("amount", 0) or 0), 2))),
                )
            )
        except (TypeError, ValueError):
            continue
    bars.sort(key=lambda b: b.bar_time)
    return bars
