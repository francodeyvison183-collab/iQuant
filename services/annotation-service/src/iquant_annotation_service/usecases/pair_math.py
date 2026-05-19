"""标注买卖对收益计算（纯函数，便于单测）。"""
from __future__ import annotations

from decimal import Decimal

from iquant_domain.errors import ValidationError


def compute_pair_return_pct(buy_close: Decimal, sell_close: Decimal) -> Decimal:
    if buy_close <= 0:
        raise ValidationError("买入价必须大于 0")
    raw = (sell_close - buy_close) / buy_close
    return raw.quantize(Decimal("1.0000000000"))
