"""会话区间 K 线加载（仅服务端，禁止向客户端泄露全量）。"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from iquant_domain.market import KlinePeriod
from iquant_market_service.usecases.query_bars import query_bars
from iquant_market_service.usecases.schemas import BarPoint

from ..config import get_blind_replay_settings

# 各周期一根 K 线的时间长度；用于跨周期对齐"截至此刻"的可见窗口。
_PERIOD_DURATION_SECONDS: dict[str, int] = {
    "5m": 5 * 60,
    "30m": 30 * 60,
    "day": 24 * 3600,
    "week": 7 * 24 * 3600,
    "month": 31 * 24 * 3600,
}


def period_duration(period: str) -> timedelta:
    seconds = _PERIOD_DURATION_SECONDS.get(period.strip(), 24 * 3600)
    return timedelta(seconds=seconds)


def view_end_time(cursor_bar_time: datetime, cursor_period: str) -> datetime:
    """cursor 所在 K 线的"区间结束时刻"。

    cursor 含义是"用户当前看到的最后一根 K 线的 bar_time"，本期 K 线
    在 ``view_end_time`` 时刻结束。任何周期视图均以此时刻为对齐基准。
    """
    return cursor_bar_time + period_duration(cursor_period)


def _parse_period(period: str) -> KlinePeriod:
    try:
        return KlinePeriod(period.strip())
    except ValueError:
        return KlinePeriod.DAY


async def load_session_bars(
    *,
    full_code: str,
    period: str,
    range_start: datetime,
    range_end: datetime,
) -> list[BarPoint]:
    """加载会话固定区间内的全部 K 线（升序）。"""
    kp = _parse_period(period)
    result = await query_bars(
        full_code=full_code.strip(),
        period=kp,
        start=range_start,
        end=range_end,
        limit=5000,
    )
    bars = sorted(result.bars, key=lambda b: b.bar_time)
    return [b for b in bars if range_start <= b.bar_time <= range_end]


async def resolve_session_range(
    *,
    full_code: str,
    period: str,
    months_back: int | None = None,
    range_start: datetime | None = None,
    range_end: datetime | None = None,
) -> list[BarPoint]:
    """创建会话时解析区间。

    传入 ``range_start`` / ``range_end`` 时使用显式日期；否则按 ``months_back`` 取近端。
    """
    cfg = get_blind_replay_settings()
    kp = _parse_period(period)

    if range_start is not None and range_end is not None:
        if range_end <= range_start:
            raise ValueError("结束日期必须晚于开始日期")
        start, end = range_start, range_end
        scope_desc = (
            f"{start.date().isoformat()} ~ {end.date().isoformat()}"
        )
    else:
        months = months_back if months_back is not None else cfg.default_months_back
        end = datetime.now(tz=UTC)
        start = end - timedelta(days=months * 31)
        scope_desc = f"近 {months} 个月"

    result = await query_bars(
        full_code=full_code.strip(),
        period=kp,
        start=start,
        end=end,
        limit=5000,
    )
    bars = sorted(result.bars, key=lambda b: b.bar_time)
    if len(bars) < cfg.min_bars_in_range:
        msg = f"标的 {full_code} {scope_desc} K 线不足 {cfg.min_bars_in_range} 根"
        raise ValueError(msg)
    return bars


def slice_visible_bars(
    bars: list[BarPoint],
    *,
    cursor_bar_time: datetime,
    cursor_period: str,
    max_visible: int,
) -> list[BarPoint]:
    """仅返回截止时刻 ``view_end_time`` 之前的 K 线，并限制图表窗口长度。"""
    end = view_end_time(cursor_bar_time, cursor_period)
    visible = [b for b in bars if b.bar_time < end]
    if len(visible) <= max_visible:
        return visible
    return visible[-max_visible:]


def cursor_index(bars: list[BarPoint], cursor_bar_time: datetime) -> int:
    for i, b in enumerate(bars):
        if b.bar_time == cursor_bar_time:
            return i
    return -1


def visible_bar_idx(
    bars: list[BarPoint], cursor_bar_time: datetime, cursor_period: str
) -> int:
    """跨周期对齐：返回最后一根 ``bar_time < view_end_time`` 的下标。

    cursor 在某周期上推进时，``view_end_time`` 标记该周期 K 线的收盘时刻。
    任何视图周期 Q 都以同一收盘时刻为右边界，使得切换周期后可见区间
    的"最新时间"与当前 K 线对齐。
    """
    end = view_end_time(cursor_bar_time, cursor_period)
    found = -1
    for i, b in enumerate(bars):
        if b.bar_time < end:
            found = i
        else:
            break
    return found


def bar_point_to_out(b: BarPoint) -> dict[str, object]:
    return {
        "bar_time": b.bar_time,
        "open": str(b.open),
        "high": str(b.high),
        "low": str(b.low),
        "close": str(b.close),
        "volume": int(b.volume),
        "amount": str(b.amount),
    }
