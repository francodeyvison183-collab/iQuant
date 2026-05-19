"""可见 K 线裁剪（禁止泄露未来 bar）。"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from iquant_market_service.usecases.schemas import BarPoint

from iquant_blind_replay_service.usecases.bar_loader import slice_visible_bars


def _bar(offset: int) -> BarPoint:
    t = datetime(2025, 1, 1, tzinfo=UTC) + timedelta(days=offset)
    return BarPoint(
        bar_time=t,
        open=Decimal("10"),
        high=Decimal("11"),
        low=Decimal("9"),
        close=Decimal("10.5"),
        volume=1000,
        amount=Decimal("10000"),
    )


def test_slice_visible_bars_never_after_cursor() -> None:
    bars = [_bar(i) for i in range(30)]
    cursor = bars[15].bar_time
    visible = slice_visible_bars(
        bars, cursor_bar_time=cursor, cursor_period="day", max_visible=200
    )
    assert all(b.bar_time <= cursor for b in visible)
    assert visible[-1].bar_time == cursor
    assert len(visible) == 16


def test_slice_visible_bars_window_cap() -> None:
    bars = [_bar(i) for i in range(100)]
    cursor = bars[99].bar_time
    visible = slice_visible_bars(
        bars, cursor_bar_time=cursor, cursor_period="day", max_visible=40
    )
    assert len(visible) == 40
    assert visible[0].bar_time == bars[60].bar_time
