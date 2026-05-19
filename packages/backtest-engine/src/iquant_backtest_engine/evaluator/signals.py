"""DSL → 每根 bar 的入场/出场意图（收盘判定，无未来函数）。"""
from __future__ import annotations

import pandas as pd
from iquant_indicators.ta import sma
from iquant_strategy_dsl import BehaviorStrategyDSL
from iquant_strategy_dsl.models import IndicatorRef, RuleClause

from ..types import OhlcBar


def _series_for_ref(
    ref: IndicatorRef,
    *,
    close: pd.Series,
    ma_cache: dict[int, pd.Series],
) -> pd.Series:
    if ref.indicator == "close":
        return close
    period = int(ref.params.get("period", 20))
    if period not in ma_cache:
        ma_cache[period] = sma(close, length=period)
    return ma_cache[period]


def _cross_above(left: pd.Series, right: pd.Series) -> pd.Series:
    prev_l = left.shift(1)
    prev_r = right.shift(1)
    return (prev_l <= prev_r) & (left > right)


def _cross_below(left: pd.Series, right: pd.Series) -> pd.Series:
    prev_l = left.shift(1)
    prev_r = right.shift(1)
    return (prev_l >= prev_r) & (left < right)


def evaluate_rule(clause: RuleClause, *, close: pd.Series, ma_cache: dict[int, pd.Series]) -> pd.Series:
    if clause.type == "hold_days_max":
        return pd.Series(False, index=close.index)

    left = _series_for_ref(clause.left, close=close, ma_cache=ma_cache)
    if clause.right is not None:
        right = _series_for_ref(clause.right, close=close, ma_cache=ma_cache)
    else:
        right = close * 0

    if clause.type == "cross_above":
        return _cross_above(left, right).fillna(False)
    if clause.type == "cross_below":
        return _cross_below(left, right).fillna(False)
    return pd.Series(False, index=close.index)


def build_entry_exit_masks(
    dsl: BehaviorStrategyDSL,
    bars: list[OhlcBar],
) -> tuple[pd.Series, pd.Series]:
    """返回与 bars 对齐的 entry_mask、exit_mask（bool）。"""
    if len(bars) < 30:
        msg = f"K 线不足 30 根，当前 {len(bars)} 根"
        raise ValueError(msg)

    close = pd.Series([b.close for b in bars], dtype=float)
    ma_cache: dict[int, pd.Series] = {}
    entry_mask = evaluate_rule(dsl.entry, close=close, ma_cache=ma_cache)
    exit_mask = evaluate_rule(dsl.exit, close=close, ma_cache=ma_cache)
    return entry_mask, exit_mask
