"""回测可复现性。"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from iquant_backtest_engine import OhlcBar, run_behavior_backtest
from iquant_strategy_dsl import build_template_dsl


def _synthetic_bars(n: int = 120) -> list[OhlcBar]:
    bars: list[OhlcBar] = []
    price = 10.0
    for i in range(n):
        t = datetime(2024, 1, 2, tzinfo=UTC) + timedelta(days=i)
        price += 0.05 if i % 7 < 4 else -0.02
        bars.append(
            OhlcBar(
                bar_time=t,
                open=price,
                high=price + 0.2,
                low=price - 0.2,
                close=price,
            )
        )
    return bars


def test_run_behavior_backtest_reproducible() -> None:
    dsl = build_template_dsl(
        template_id="ma_breakout",
        name="测试",
        period="day",
        fit_score=0.8,
        blind_session_count=3,
    )
    bars = _synthetic_bars()
    r1 = run_behavior_backtest(dsl_doc=dsl, bars=bars)
    r2 = run_behavior_backtest(dsl_doc=dsl, bars=bars)
    assert r1.summary["trade_count"] == r2.summary["trade_count"]
    assert r1.summary["total_return_raw"] == r2.summary["total_return_raw"]
    assert len(r1.equity_curve) == len(bars)
