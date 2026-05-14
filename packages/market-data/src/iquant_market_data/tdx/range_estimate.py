"""按区间估算 TDX 首页 ``count``，减少固定 800 根造成的浪费。

逻辑对齐 ``HQScanner.app.services.tdx_service.fetch_kline_paged``：用日历跨度粗估交易日数，
再乘以该周期「每交易日 bar 数」；无交易日历服务时用 ``span * 5/7`` 退化估算。
"""
from __future__ import annotations

from datetime import datetime

from iquant_domain.market import KlinePeriod

TDX_PAGE_SIZE = 800

_BARS_PER_TRADING_DAY: dict[KlinePeriod, int] = {
    KlinePeriod.MIN_1: 240,
    KlinePeriod.MIN_5: 48,
    KlinePeriod.MIN_15: 16,
    KlinePeriod.MIN_30: 8,
    KlinePeriod.MIN_60: 4,
    KlinePeriod.DAY: 1,
}


def estimate_first_page_count(*, period: KlinePeriod, start: datetime, end: datetime) -> int:
    """估算从 ``start`` 到 ``end``（通常到「今天」）需要向 TDX 拉多少根才能覆盖区间左端。

    +2 根容错与 HQScanner 一致；结果限制在 ``[4, 800]``。
    """
    start0 = start.replace(hour=0, minute=0, second=0, microsecond=0)
    end0 = end.replace(hour=0, minute=0, second=0, microsecond=0)
    if start0 > end0:
        start0 = end0
    span_days = max((end0 - start0).days + 1, 1)
    td_count = max(int(span_days * 5 / 7), 1)

    if period == KlinePeriod.WEEK:
        need = max(span_days // 7 + 2, 4)
    elif period == KlinePeriod.MONTH:
        need = max(span_days // 30 + 2, 4)
    else:
        bpd = _BARS_PER_TRADING_DAY.get(period, 1)
        need = td_count * bpd

    return min(max(need + 2, 4), TDX_PAGE_SIZE)
