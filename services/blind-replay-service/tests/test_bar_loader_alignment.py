"""跨周期视图对齐：visible_bar_idx / slice_visible_bars。"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from iquant_blind_replay_service.usecases.bar_loader import (
    slice_visible_bars,
    view_end_time,
    visible_bar_idx,
)
from iquant_market_service.usecases.schemas import BarPoint


def _bar(t: datetime) -> BarPoint:
    return BarPoint(
        bar_time=t,
        open=Decimal("10"),
        high=Decimal("10"),
        low=Decimal("10"),
        close=Decimal("10"),
        volume=100,
        amount=Decimal("1000"),
    )


def _daily_bars(n: int, start: datetime) -> list[BarPoint]:
    return [_bar(start + timedelta(days=i)) for i in range(n)]


def _five_min_bars_for_day(day: datetime) -> list[BarPoint]:
    bars: list[BarPoint] = []
    start_intraday = day.replace(hour=1, minute=30)  # 模拟 09:30 上海时间
    for k in range(48):
        bars.append(_bar(start_intraday + timedelta(minutes=5 * k)))
    return bars


def test_view_end_time_daily_is_next_day_start() -> None:
    t = datetime(2024, 1, 15, tzinfo=UTC)
    assert view_end_time(t, "day") == datetime(2024, 1, 16, tzinfo=UTC)


def test_visible_bar_idx_same_period_daily() -> None:
    bars = _daily_bars(10, datetime(2024, 1, 1, tzinfo=UTC))
    cursor = bars[3].bar_time
    idx = visible_bar_idx(bars, cursor, "day")
    assert idx == 3
    assert bars[idx].bar_time == cursor


def test_visible_bar_idx_cross_period_day_cursor_to_5m_view() -> None:
    """cursor 在日线 D 上时，切换 5m 应可见 D 当天所有 5m。"""
    day_d = datetime(2024, 1, 15, tzinfo=UTC)
    five_m_bars = (
        _five_min_bars_for_day(day_d - timedelta(days=1))
        + _five_min_bars_for_day(day_d)
        + _five_min_bars_for_day(day_d + timedelta(days=1))
    )
    idx = visible_bar_idx(five_m_bars, day_d, "day")
    assert idx >= 0
    # 期望：最后一根可见 5m 仍在 D 这一天（< 00:00 D+1）
    assert five_m_bars[idx].bar_time < day_d + timedelta(days=1)
    # D 当天最后一根 5m 应可见
    last_5m_of_d = (day_d.replace(hour=1, minute=30)) + timedelta(minutes=5 * 47)
    assert any(b.bar_time == last_5m_of_d for b in five_m_bars[: idx + 1])
    # D+1 的第一根 5m 不可见
    first_d_plus_1 = (day_d + timedelta(days=1)).replace(hour=1, minute=30)
    assert all(b.bar_time != first_d_plus_1 for b in five_m_bars[: idx + 1])


def test_slice_visible_bars_strict_below_end() -> None:
    bars = _daily_bars(10, datetime(2024, 1, 1, tzinfo=UTC))
    cursor = bars[5].bar_time
    visible = slice_visible_bars(
        bars, cursor_bar_time=cursor, cursor_period="day", max_visible=100
    )
    assert len(visible) == 6  # bars[0..5]
    assert visible[-1].bar_time == cursor
