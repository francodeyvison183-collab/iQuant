"""empyrical-reloaded 封装烟测。"""
from __future__ import annotations

from iquant_backtest_engine.metrics.performance import max_drawdown, sharpe_ratio


def test_sharpe_and_drawdown_smoke() -> None:
    curve = [100.0, 101.0, 100.5, 102.0, 101.0, 103.0]
    sh = sharpe_ratio(curve)
    dd = max_drawdown(curve)
    assert sh is not None
    assert dd is not None
    assert float(dd) <= 0
