"""首页 K 线根数估算（TDX 分页优化）。"""
from __future__ import annotations

from datetime import datetime

from iquant_domain.market import KlinePeriod

from iquant_market_data.tdx.range_estimate import estimate_first_page_count


def test_daily_span():
    start = datetime(2024, 1, 1)
    n = estimate_first_page_count(period=KlinePeriod.DAY, start=start)
    assert 4 <= n <= 800


def test_intraday_5m():
    start = datetime(2024, 1, 1)
    n = estimate_first_page_count(period=KlinePeriod.MIN_5, start=start)
    assert n <= 800
    assert n >= 4


def test_week_month():
    start = datetime(2023, 1, 1)
    w = estimate_first_page_count(period=KlinePeriod.WEEK, start=start)
    m = estimate_first_page_count(period=KlinePeriod.MONTH, start=start)
    assert 4 <= w <= 800
    assert 4 <= m <= 800
