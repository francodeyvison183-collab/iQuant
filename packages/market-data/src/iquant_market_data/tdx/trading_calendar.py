"""A 股交易日历（上交所 ``XSHG``，深沪共用）。

优先使用 ``exchange-calendars``；不可用时退化为工作日 × 5/7 粗估（与旧逻辑兼容）。
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

logger = logging.getLogger(__name__)

_CALENDAR_ID = "XSHG"
_cal = None
_cal_available: bool | None = None


def _get_calendar():  # type: ignore[no-untyped-def]
    global _cal, _cal_available
    if _cal_available is False:
        return None
    if _cal is not None:
        return _cal
    try:
        import exchange_calendars as xcals

        _cal = xcals.get_calendar(_CALENDAR_ID)
        _cal_available = True
        return _cal
    except Exception as exc:  # noqa: BLE001
        logger.warning("trading_calendar_unavailable", extra={"error": str(exc)})
        _cal_available = False
        return None


def count_trading_days(start: date | datetime, end: date | datetime) -> int:
    """闭区间 ``[start, end]`` 内的交易日数量（按日历日）。"""
    start_d = start.date() if isinstance(start, datetime) else start
    end_d = end.date() if isinstance(end, datetime) else end
    if start_d > end_d:
        start_d, end_d = end_d, start_d

    cal = _get_calendar()
    if cal is not None:
        try:
            import pandas as pd

            sessions = cal.sessions_in_range(
                pd.Timestamp(start_d),
                pd.Timestamp(end_d),
            )
            return int(len(sessions))
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "trading_calendar_range_failed",
                extra={"start": start_d.isoformat(), "end": end_d.isoformat(), "error": str(exc)},
            )

    span = (end_d - start_d).days + 1
    return max(int(span * 5 / 7), 1)


def trading_days_in_range(start: date | datetime, end: date | datetime) -> list[date]:
    """返回区间内每个交易日的 ``date`` 列表（升序）。"""
    start_d = start.date() if isinstance(start, datetime) else start
    end_d = end.date() if isinstance(end, datetime) else end
    if start_d > end_d:
        start_d, end_d = end_d, start_d

    cal = _get_calendar()
    if cal is not None:
        try:
            import pandas as pd

            sessions = cal.sessions_in_range(
                pd.Timestamp(start_d),
                pd.Timestamp(end_d),
            )
            return [s.date() for s in sessions]
        except Exception as exc:  # noqa: BLE001
            logger.warning("trading_calendar_list_failed", extra={"error": str(exc)})

    out: list[date] = []
    cur = start_d
    while cur <= end_d:
        if cur.weekday() < 5:
            out.append(cur)
        cur += timedelta(days=1)
    return out
