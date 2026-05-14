"""K 线查询用例。"""
from __future__ import annotations

from datetime import datetime

from iquant_domain.market import KlinePeriod

from ..db import ts_session
from ..repositories.market_bar_repo import MarketBarRepo
from .schemas import BarPoint, BarQueryResult, SymbolCoverage


async def query_bars(
    *,
    full_code: str,
    period: KlinePeriod,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 500,
) -> BarQueryResult:
    async with ts_session() as ts:
        rows = await MarketBarRepo(ts).query_bars(
            full_code=full_code, period=period, start=start, end=end, limit=limit
        )
    return BarQueryResult(
        full_code=full_code,
        period=period,
        bars=[
            BarPoint(
                bar_time=r.bar_time,
                open=r.open,
                high=r.high,
                low=r.low,
                close=r.close,
                volume=r.volume,
                amount=r.amount,
            )
            for r in rows
        ],
    )


async def get_symbol_coverage(*, full_code: str, period: KlinePeriod) -> SymbolCoverage:
    async with ts_session() as ts:
        first, last, count = await MarketBarRepo(ts).coverage(
            full_code=full_code, period=period
        )
    return SymbolCoverage(
        full_code=full_code,
        period=period,
        first_bar_time=first,
        last_bar_time=last,
        bar_count=count,
    )
