"""做多、次根开盘成交、费用滑点（MVP）。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd
from iquant_strategy_dsl import BehaviorStrategyDSL

from ..types import OhlcBar, TradeRecord

_FEE = 0.0005
_SLIPPAGE = 0.0005


@dataclass
class _Position:
    entry_idx: int
    entry_price: float
    entry_time: datetime


def simulate_long_only(
    *,
    bars: list[OhlcBar],
    entry_mask: pd.Series,
    exit_mask: pd.Series,
    dsl: BehaviorStrategyDSL,
    initial_cash: float,
    in_sample_end_idx: int,
) -> tuple[list[float], list[TradeRecord], list[str]]:
    """返回权益曲线（每 bar 收盘市值）、成交列表、警告。"""
    warnings: list[str] = []
    cash = initial_cash
    shares = 0.0
    pos: _Position | None = None
    equity: list[float] = []
    trades: list[TradeRecord] = []

    stop_pct = float(dsl.risk.stop_loss_pct) if dsl.risk.stop_loss_pct is not None else None
    hold_exit = dsl.exit.type == "hold_days_max" and dsl.exit.value is not None
    max_hold_days = int(dsl.exit.value) if hold_exit else dsl.risk.max_hold_days

    for i, bar in enumerate(bars):
        if i > 0:
            if shares <= 0 and bool(entry_mask.iloc[i - 1]):
                price = bar.open * (1 + _SLIPPAGE)
                if price > 0 and cash > 0:
                    shares = (cash * (1 - _FEE)) / price
                    cash = 0.0
                    pos = _Position(entry_idx=i, entry_price=price, entry_time=bar.bar_time)
            elif shares > 0 and bool(exit_mask.iloc[i - 1]):
                price = bar.open * (1 - _SLIPPAGE)
                cash = shares * price * (1 - _FEE)
                if pos is not None:
                    ret = (price - pos.entry_price) / pos.entry_price
                    trades.append(
                        TradeRecord(
                            entry_time=pos.entry_time,
                            exit_time=bar.bar_time,
                            entry_price=pos.entry_price,
                            exit_price=price,
                            return_pct=ret,
                        )
                    )
                shares = 0.0
                pos = None

        if shares > 0 and pos is not None and i > pos.entry_idx:
            hold_days = i - pos.entry_idx
            exited = False
            if stop_pct is not None:
                stop_price = pos.entry_price * (1 - stop_pct)
                if bar.low <= stop_price:
                    price = stop_price * (1 - _SLIPPAGE)
                    cash = shares * price * (1 - _FEE)
                    ret = (price - pos.entry_price) / pos.entry_price
                    trades.append(
                        TradeRecord(
                            entry_time=pos.entry_time,
                            exit_time=bar.bar_time,
                            entry_price=pos.entry_price,
                            exit_price=price,
                            return_pct=ret,
                        )
                    )
                    shares = 0.0
                    pos = None
                    exited = True
            if not exited and max_hold_days is not None and hold_days >= max_hold_days:
                price = bar.close * (1 - _SLIPPAGE)
                cash = shares * price * (1 - _FEE)
                ret = (price - pos.entry_price) / pos.entry_price
                trades.append(
                    TradeRecord(
                        entry_time=pos.entry_time,
                        exit_time=bar.bar_time,
                        entry_price=pos.entry_price,
                        exit_price=price,
                        return_pct=ret,
                    )
                )
                shares = 0.0
                pos = None

        equity.append(cash + shares * bar.close)

    if shares > 0 and pos is not None:
        last = bars[-1]
        price = last.close * (1 - _SLIPPAGE)
        cash = shares * price * (1 - _FEE)
        ret = (price - pos.entry_price) / pos.entry_price
        trades.append(
            TradeRecord(
                entry_time=pos.entry_time,
                exit_time=last.bar_time,
                entry_price=pos.entry_price,
                exit_price=price,
                return_pct=ret,
            )
        )
        equity[-1] = cash
        warnings.append("回测结束仍有持仓，已按最后一根收盘价平仓。")

    if not trades:
        warnings.append("回测区间内未产生完整买卖回合，请检查 DSL 或延长区间。")

    if in_sample_end_idx < len(bars) - 10 and len(trades) < 2:
        warnings.append("样本外区间较短或交易过少，样本外指标仅供参考。")

    return equity, trades, warnings
