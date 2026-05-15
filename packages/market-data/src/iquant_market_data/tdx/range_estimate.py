"""按区间估算 TDX 首页 ``count``，减少固定 800 根造成的浪费。

用 ``exchange-calendars`` 统计区间交易日数，再乘以该周期「每交易日 bar 数」；
日历不可用时用 ``span * 5/7`` 退化估算。
"""
from __future__ import annotations

from datetime import datetime

from iquant_domain.market import KlinePeriod

from .trading_calendar import count_trading_days

TDX_PAGE_SIZE = 800

_BARS_PER_TRADING_DAY: dict[KlinePeriod, int] = {
    KlinePeriod.MIN_1: 240,
    KlinePeriod.MIN_5: 48,
    KlinePeriod.MIN_15: 16,
    KlinePeriod.MIN_30: 8,
    KlinePeriod.MIN_60: 4,
    KlinePeriod.DAY: 1,
}


def estimate_first_page_count(*, period: KlinePeriod, start: datetime) -> int:
    """估算从 ``start`` 到**今天**需拉多少根才能覆盖区间左端。

    TDX ``start=0`` 锚定最新交易日；``end_date`` 不参与首页 count（拉取后按区间过滤）。
    +2 根容错；结果限制在 ``[4, 800]``。
    """
    start0 = start.replace(hour=0, minute=0, second=0, microsecond=0)
    today0 = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if start0 > today0:
        start0 = today0
    td_count = count_trading_days(start0.date(), today0.date())
    span_days = max((today0 - start0).days + 1, 1)

    if period == KlinePeriod.WEEK:
        need = max(span_days // 7 + 2, 4)
    elif period == KlinePeriod.MONTH:
        need = max(span_days // 30 + 2, 4)
    else:
        bpd = _BARS_PER_TRADING_DAY.get(period, 1)
        need = td_count * bpd

    return min(max(need + 2, 4), TDX_PAGE_SIZE)
