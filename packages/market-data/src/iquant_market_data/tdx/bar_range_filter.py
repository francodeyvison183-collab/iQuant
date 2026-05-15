"""按用户区间过滤 K 线（日线闭区间、分钟线半开区间）。"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from iquant_domain.market import KlinePeriod, MarketBar


def filter_bars_in_date_range(
    bars: list[MarketBar],
    *,
    period: KlinePeriod,
    start: datetime,
    end: datetime | None,
) -> list[MarketBar]:
    """日线/周线/月线：按自然日闭区间；分钟线：``[start 0:00, end 日+1 0:00)`` 半开区间。"""
    start_dt = start.replace(hour=0, minute=0, second=0, microsecond=0)
    if end is None:
        end_exclusive = datetime.combine(date.today(), time.min) + timedelta(days=1)
    else:
        end_exclusive = datetime.combine(end.date(), time.min) + timedelta(days=1)

    if period in (KlinePeriod.DAY, KlinePeriod.WEEK, KlinePeriod.MONTH):
        end_inclusive = end_exclusive.date() - timedelta(days=1)
        return [
            b
            for b in bars
            if start_dt.date() <= b.bar_time.date() <= end_inclusive
        ]
    return [b for b in bars if start_dt <= b.bar_time < end_exclusive]
