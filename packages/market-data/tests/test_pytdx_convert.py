"""pytdx 记录转换测试。"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from iquant_domain.market import KlinePeriod
from iquant_market_data.tdx.pytdx_convert import bars_from_pytdx, parse_pytdx_datetime


def test_parse_pytdx_datetime_formats() -> None:
    assert parse_pytdx_datetime("2024-06-01 10:30") == datetime(2024, 6, 1, 10, 30)
    assert parse_pytdx_datetime("2024-06-01") == datetime(2024, 6, 1, 0, 0)


def test_bars_from_pytdx() -> None:
    raw = [
        {
            "datetime": "2024-01-02 15:00",
            "open": 10.0,
            "high": 11.0,
            "low": 9.5,
            "close": 10.5,
            "vol": 1000,
            "amount": 12345.6,
        }
    ]
    bars = bars_from_pytdx(raw, full_code="sh600519", period=KlinePeriod.DAY)
    assert len(bars) == 1
    b = bars[0]
    assert b.full_code == "sh600519"
    assert b.close == Decimal("10.5")
    assert b.volume == 1000
