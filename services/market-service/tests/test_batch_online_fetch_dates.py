"""批量在线更新日期边界。"""
from __future__ import annotations

from datetime import date, datetime, time

from iquant_domain.market import KlinePeriod, MarketBar
from iquant_market_data.tdx.bar_range_filter import filter_bars_in_date_range
from iquant_market_service.usecases.batch_online_fetch import _parse_iso_date, _parse_range_end


def test_parse_range_end_includes_full_day() -> None:
    end = _parse_range_end("2024-01-31")
    assert end is not None
    assert end.hour == 23
    assert end.minute == 59
    bar = MarketBar(
        full_code="sh600519",
        period=KlinePeriod.DAY,
        bar_time=datetime(2024, 1, 31, 15, 0),
        open=1,
        high=1,
        low=1,
        close=1,
        volume=0,
        amount=0,
    )
    start = _parse_iso_date("2024-01-01")
    assert start is not None
    filtered = filter_bars_in_date_range(
        [bar], period=KlinePeriod.DAY, start=start, end=end
    )
    assert len(filtered) == 1


def test_same_day_range_includes_intraday() -> None:
    start = _parse_iso_date("2024-06-01")
    end = _parse_range_end("2024-06-01")
    assert start is not None and end is not None
    bar = MarketBar(
        full_code="sh600519",
        period=KlinePeriod.MIN_5,
        bar_time=datetime(2024, 6, 1, 10, 30),
        open=1,
        high=1,
        low=1,
        close=1,
        volume=0,
        amount=0,
    )
    filtered = filter_bars_in_date_range(
        [bar], period=KlinePeriod.MIN_5, start=start, end=end
    )
    assert len(filtered) == 1
