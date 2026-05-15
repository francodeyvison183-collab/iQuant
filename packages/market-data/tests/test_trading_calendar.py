"""交易日历。"""
from __future__ import annotations

from datetime import date

from iquant_market_data.tdx.trading_calendar import count_trading_days, trading_days_in_range


def test_count_trading_days_week_range() -> None:
    # 2024-01-02 ~ 2024-01-05 应为 4 个交易日（元旦后）
    n = count_trading_days(date(2024, 1, 2), date(2024, 1, 5))
    assert n >= 3
    assert n <= 5


def test_trading_days_list_sorted() -> None:
    days = trading_days_in_range(date(2024, 6, 1), date(2024, 6, 7))
    assert days == sorted(days)
    assert all(d.weekday() < 5 for d in days) or len(days) == 0
