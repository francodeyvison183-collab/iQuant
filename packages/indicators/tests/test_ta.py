"""pandas-ta 封装烟测。"""
from __future__ import annotations

import pandas as pd

from iquant_indicators.ta import rsi, sma


def test_sma_rsi_smoke() -> None:
    close = pd.Series([float(i) for i in range(1, 40)])
    ma = sma(close, length=5)
    r = rsi(close, length=14)
    assert len(ma.dropna()) > 0
    assert len(r.dropna()) > 0
