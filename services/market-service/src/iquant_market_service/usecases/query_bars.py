"""K 线查询用例。"""
from __future__ import annotations

from datetime import datetime

from iquant_domain.market import KlinePeriod

from ..db import pg_session, ts_session
from ..repositories.market_bar_repo import MarketBarRepo
from ..repositories.symbol_repo import SymbolRepo
from .schemas import BarPoint, BarQueryResult, BrowserSymbolRow, SymbolCoverage


async def list_symbols(
    *,
    market: str | None = None,
    keyword: str | None = None,
    limit: int = 50,
    offset: int = 0,
    scope: str = "with_bars",
) -> tuple[list[BrowserSymbolRow], int]:
    """数据浏览用标的列表。

    - ``with_bars``（默认）：仅返回 TimescaleDB 中已有 K 线的代码（与「数据查看」语义一致）。
    - ``catalog``：返回业务库 ``symbol`` 全表（需先跑名称同步才有完整列表）。
    """
    if scope == "catalog":
        async with pg_session() as pg:
            rows, total = await SymbolRepo(pg).list_paged(
                market=market, keyword=keyword, limit=limit, offset=offset
            )
        return [
            BrowserSymbolRow(
                full_code=r.full_code,
                code=r.code,
                market=r.market,
                name=r.name or r.code,
                asset_type=r.asset_type,
            )
            for r in rows
        ], total

    async with ts_session() as ts:
        codes, total = await MarketBarRepo(ts).list_distinct_full_codes_paged(
            market=market, keyword=keyword, limit=limit, offset=offset
        )
    names: dict[str, str] = {}
    if codes:
        async with pg_session() as pg:
            names = await SymbolRepo(pg).name_map(codes)

    items: list[BrowserSymbolRow] = []
    for fc in codes:
        market_prefix = fc[:2] if len(fc) >= 8 else ""
        code6 = fc[2:8] if len(fc) >= 8 else fc
        items.append(
            BrowserSymbolRow(
                full_code=fc,
                code=code6,
                market=market_prefix,
                name=names.get(fc) or code6,
                asset_type="stock",
            )
        )
    return items, total


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


async def get_symbol_names(full_codes: list[str]) -> dict[str, str]:
    """批量取标的名称；无记录或空名称的代码不出现在结果中。"""
    if not full_codes:
        return {}
    async with pg_session() as pg:
        return await SymbolRepo(pg).name_map(full_codes)


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
