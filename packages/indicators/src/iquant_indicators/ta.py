"""技术指标薄封装：业务代码只依赖本模块，不直接散落 pandas-ta 调用。"""
from __future__ import annotations

import pandas as pd
import pandas_ta as ta


def sma(close: pd.Series, length: int = 20) -> pd.Series:
    out = ta.sma(close, length=length)
    return out if out is not None else pd.Series(dtype=float)


def rsi(close: pd.Series, length: int = 14) -> pd.Series:
    out = ta.rsi(close, length=length)
    return out if out is not None else pd.Series(dtype=float)


def macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    out = ta.macd(close, fast=fast, slow=slow, signal=signal)
    return out if out is not None else pd.DataFrame()


def atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    out = ta.atr(high, low, close, length=length)
    return out if out is not None else pd.Series(dtype=float)
