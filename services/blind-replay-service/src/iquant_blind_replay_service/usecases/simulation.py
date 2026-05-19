"""盲测模拟成交（收盘决策、次日开盘成交）。"""
from __future__ import annotations

from decimal import Decimal

from iquant_market_service.usecases.schemas import BarPoint

from ..models.blind_session import BlindSessionORM

_FEE = Decimal("0.0005")
_SLIPPAGE = Decimal("0.0005")


def apply_fill_after_decision(
    session: BlindSessionORM,
    *,
    user_action: str,
    decision_bar: BarPoint,
    fill_bar: BarPoint | None,
) -> None:
    _ = decision_bar
    """在 cursor 推进到 fill_bar 时，按上一根决策 bar 的意图成交。"""
    if fill_bar is None or user_action == "hold":
        return
    if user_action == "buy" and session.position_qty <= 0 and session.cash_balance > 0:
        price = fill_bar.open * (Decimal("1") + _SLIPPAGE)
        if price <= 0:
            return
        gross = session.cash_balance * (Decimal("1") - _FEE)
        session.position_qty = gross / price
        session.cash_balance = Decimal("0")
    elif user_action == "sell" and session.position_qty > 0:
        price = fill_bar.open * (Decimal("1") - _SLIPPAGE)
        if price <= 0:
            return
        gross = session.position_qty * price * (Decimal("1") - _FEE)
        session.cash_balance = gross
        session.position_qty = Decimal("0")
