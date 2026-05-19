"""盲测模拟成交单测。"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from iquant_blind_replay_service.usecases.simulation import apply_fill_after_decision
from iquant_market_service.usecases.schemas import BarPoint


def _bar(t: datetime, o: str, c: str) -> BarPoint:
    open_ = Decimal(o)
    close = Decimal(c)
    return BarPoint(
        bar_time=t,
        open=open_,
        high=open_,
        low=open_,
        close=close,
        volume=100,
        amount=open_ * 100,
    )


def test_apply_fill_buy_at_next_open() -> None:
    session = SimpleNamespace(
        cash_balance=Decimal("100000"),
        position_qty=Decimal("0"),
    )
    decision = _bar(datetime(2024, 1, 2, tzinfo=UTC), "10", "10.5")
    fill = _bar(datetime(2024, 1, 3, tzinfo=UTC), "11", "11.2")
    apply_fill_after_decision(
        session,
        user_action="buy",
        decision_bar=decision,
        fill_bar=fill,
    )
    assert session.cash_balance == Decimal("0")
    assert session.position_qty > 0


def test_apply_fill_hold_unchanged() -> None:
    session = SimpleNamespace(
        cash_balance=Decimal("100000"),
        position_qty=Decimal("0"),
    )
    decision = _bar(datetime(2024, 1, 2, tzinfo=UTC), "10", "10")
    fill = _bar(datetime(2024, 1, 3, tzinfo=UTC), "11", "11")
    apply_fill_after_decision(
        session,
        user_action="hold",
        decision_bar=decision,
        fill_bar=fill,
    )
    assert session.cash_balance == Decimal("100000")
    assert session.position_qty == Decimal("0")
