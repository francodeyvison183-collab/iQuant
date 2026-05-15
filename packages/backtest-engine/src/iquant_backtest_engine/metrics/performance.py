"""收益风险指标：统一走 empyrical-reloaded，禁止手写标准公式。"""
from __future__ import annotations

from decimal import Decimal
from typing import Sequence

import empyrical as ep
import numpy as np
import pandas as pd


def _to_returns(series: Sequence[float] | pd.Series) -> pd.Series:
    s = pd.Series(series, dtype=float)
    if s.empty:
        return s
    return s.pct_change().dropna()


def sharpe_ratio(
    equity_curve: Sequence[float] | pd.Series,
    *,
    risk_free: float = 0.0,
    period: str = "daily",
) -> Decimal | None:
    """年化 Sharpe（基于净值或价格序列的收益率）。"""
    rets = _to_returns(equity_curve)
    if rets.empty:
        return None
    val = ep.sharpe_ratio(rets, risk_free=risk_free, period=period)
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    return Decimal(str(round(float(val), 6)))


def max_drawdown(equity_curve: Sequence[float] | pd.Series) -> Decimal | None:
    """最大回撤（比例，负数；输入为净值/权益曲线）。"""
    s = pd.Series(equity_curve, dtype=float)
    if len(s) < 2:
        return None
    rets = s.pct_change().dropna()
    if rets.empty:
        return None
    val = ep.max_drawdown(rets)
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    return Decimal(str(round(float(val), 6)))
