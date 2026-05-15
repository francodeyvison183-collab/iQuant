"""K 线区间过滤。"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from iquant_domain.market import KlinePeriod, MarketBar
from iquant_market_data.tdx.bar_range_filter import filter_bars_in_date_range


def _bar(when: datetime) -> MarketBar:
    return MarketBar(
        full_code="sh600519",
        period=KlinePeriod.DAY,
        bar_time=when,
        open=Decimal(1),
        high=Decimal(1),
        low=Decimal(1),
        close=Decimal(1),
        volume=0,
        amount=Decimal(0),
    )


def test_daily_includes_end_day_close() -> None:
    bars = [
        _bar(datetime(2024, 1, 30, 15, 0)),
        _bar(datetime(2024, 1, 31, 15, 0)),
        _bar(datetime(2024, 2, 1, 15, 0)),
    ]
    out = filter_bars_in_date_range(
        bars,
        period=KlinePeriod.DAY,
        start=datetime(2024, 1, 1),
        end=datetime(2024, 1, 31, 23, 59, 59),
    )
    assert len(out) == 2
    assert out[-1].bar_time.day == 31


def test_minute_half_open_end() -> None:
    bars = [
        MarketBar(
            full_code="sh600519",
            period=KlinePeriod.MIN_5,
            bar_time=datetime(2024, 6, 1, 10, 30),
            open=Decimal(1),
            high=Decimal(1),
            low=Decimal(1),
            close=Decimal(1),
            volume=0,
            amount=Decimal(0),
        ),
        MarketBar(
            full_code="sh600519",
            period=KlinePeriod.MIN_5,
            bar_time=datetime(2024, 6, 2, 10, 30),
            open=Decimal(1),
            high=Decimal(1),
            low=Decimal(1),
            close=Decimal(1),
            volume=0,
            amount=Decimal(0),
        ),
    ]
    out = filter_bars_in_date_range(
        bars,
        period=KlinePeriod.MIN_5,
        start=datetime(2024, 6, 1),
        end=datetime(2024, 6, 1, 23, 59, 59),
    )
    assert len(out) == 1
    assert out[0].bar_time.day == 1
