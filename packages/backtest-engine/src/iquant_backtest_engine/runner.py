"""回测编排入口。"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from iquant_strategy_dsl import BehaviorStrategyDSL, validate_dsl

from .evaluator import build_entry_exit_masks
from .execution import simulate_long_only
from .metrics.performance import max_drawdown
from .types import BacktestRunResult, OhlcBar


def _pct_str(v: float) -> str:
    sign = "+" if v >= 0 else ""
    return f"{sign}{v * 100:.2f}%"


def _slice_return(equity: list[float], start: int, end: int) -> float | None:
    if end <= start or start < 0 or end >= len(equity):
        return None
    base = equity[start]
    if base <= 0:
        return None
    return (equity[end] - base) / base


def run_behavior_backtest(
    *,
    dsl_doc: dict[str, object] | BehaviorStrategyDSL,
    bars: list[OhlcBar],
    initial_cash: float = 1_000_000.0,
    in_sample_ratio: float = 0.7,
) -> BacktestRunResult:
    """对已确认 DSL 与 K 线序列执行回测（可复现）。"""
    dsl = validate_dsl(dsl_doc)
    if len(bars) < 40:
        raise ValueError(f"K 线不足 40 根，当前 {len(bars)} 根")

    entry_mask, exit_mask = build_entry_exit_masks(dsl, bars)
    split = max(20, int(len(bars) * in_sample_ratio))
    split = min(split, len(bars) - 10)

    equity, trades, warnings = simulate_long_only(
        bars=bars,
        entry_mask=entry_mask,
        exit_mask=exit_mask,
        dsl=dsl,
        initial_cash=initial_cash,
        in_sample_end_idx=split,
    )

    total_ret = (equity[-1] - initial_cash) / initial_cash if initial_cash > 0 else 0.0
    in_ret = _slice_return(equity, 0, split) or 0.0
    out_ret = _slice_return(equity, split, len(equity) - 1) or 0.0
    wins = sum(1 for t in trades if t.return_pct > 0)
    win_rate = wins / len(trades) if trades else 0.0
    mdd = max_drawdown(equity)
    mdd_f = float(mdd) if mdd is not None else 0.0

    curve = [
        {
            "bar_time": bars[i].bar_time.isoformat(),
            "equity": round(equity[i], 2),
        }
        for i in range(len(bars))
    ]

    window = {
        "in_sample_start": bars[0].bar_time.isoformat(),
        "in_sample_end": bars[split].bar_time.isoformat(),
        "out_sample_start": bars[split + 1].bar_time.isoformat(),
        "out_sample_end": bars[-1].bar_time.isoformat(),
        "split_index": split,
    }

    summary: dict[str, object] = {
        "total_return": _pct_str(total_ret),
        "total_return_raw": round(total_ret, 6),
        "in_sample_return": _pct_str(in_ret),
        "out_sample_return": _pct_str(out_ret),
        "max_drawdown": _pct_str(mdd_f),
        "max_drawdown_raw": round(mdd_f, 6),
        "win_rate": f"{win_rate * 100:.1f}%",
        "trade_count": len(trades),
        "initial_cash": initial_cash,
        "final_equity": round(equity[-1], 2),
        "strategy_name": dsl.name,
        "period": dsl.period,
    }

    return BacktestRunResult(
        summary=summary,
        equity_curve=curve,
        trades=trades,
        data_window=window,
        warnings=warnings,
    )


def bars_from_market(
    rows: list[object],
) -> list[OhlcBar]:
    """从 market-service BarPoint 列表转换。"""
    out: list[OhlcBar] = []
    for r in rows:
        bt = getattr(r, "bar_time", None)
        if isinstance(bt, datetime):
            t = bt
        else:
            t = datetime.fromisoformat(str(bt).replace("Z", "+00:00"))
        out.append(
            OhlcBar(
                bar_time=t,
                open=float(getattr(r, "open")),
                high=float(getattr(r, "high")),
                low=float(getattr(r, "low")),
                close=float(getattr(r, "close")),
            )
        )
    return out
