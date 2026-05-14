"""领域模型测试。"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from iquant_domain.market import KlinePeriod, Market, MarketBar, MarketBarBatch, Symbol


def test_symbol_full_code():
    s = Symbol(code="600519", market=Market.SH, name="贵州茅台")
    assert s.full_code == "sh600519"


def test_symbol_validates_code_digits():
    with pytest.raises(ValueError):
        Symbol(code="60051A", market=Market.SH, name="x")


def test_kline_period_intraday():
    assert KlinePeriod.MIN_5.is_intraday is True
    assert KlinePeriod.DAY.is_intraday is False


def test_market_bar_high_low_validation():
    with pytest.raises(ValueError):
        MarketBar(
            full_code="sh600519",
            period=KlinePeriod.DAY,
            bar_time=datetime(2026, 1, 1),
            open=Decimal("10"),
            high=Decimal("9"),
            low=Decimal("11"),
            close=Decimal("10"),
            volume=1000,
            amount=Decimal("10000"),
        )


def test_market_bar_batch_len():
    bar = MarketBar(
        full_code="sh600519",
        period=KlinePeriod.DAY,
        bar_time=datetime(2026, 1, 1),
        open=Decimal("10"),
        high=Decimal("11"),
        low=Decimal("9"),
        close=Decimal("10.5"),
        volume=100,
        amount=Decimal("1000"),
    )
    batch = MarketBarBatch(full_code="sh600519", period=KlinePeriod.DAY, bars=[bar, bar])
    assert len(batch) == 2
    assert not batch.is_empty


def test_market_bar_batch_empty():
    batch = MarketBarBatch(full_code="sh600519", period=KlinePeriod.DAY, bars=[])
    assert batch.is_empty
