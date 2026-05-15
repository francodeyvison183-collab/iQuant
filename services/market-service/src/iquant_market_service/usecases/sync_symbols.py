"""标的名称维护：从 TDX 全市场列表同步至业务库 ``symbol`` 表。

与代码解析同源（``list_a_share_stocks`` / pytdx），保证在线批量、本地导入、数据浏览共用一套名称。
"""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from iquant_domain.market import Symbol
from iquant_market_data.tdx.a_share_list import list_a_share_stocks
from iquant_market_data.tdx.codes import split_full_code

from ..db import pg_session
from ..repositories.symbol_repo import SymbolRepo

if TYPE_CHECKING:
    from iquant_market_data.tdx.pool import TdxConnectionPool

logger = logging.getLogger(__name__)

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def sanitize_stock_name(name: str, full_code: str) -> str:
    """清洗 TDX 返回的名称；无效时回退为 6 位代码。"""
    normalized = (name or "").strip()
    code6 = full_code[-6:] if len(full_code) >= 6 else full_code
    if not normalized or normalized == full_code or normalized == code6:
        return code6
    if not _CJK_RE.search(normalized):
        return code6
    return normalized[:64]


async def fetch_a_share_pairs(*, pool: TdxConnectionPool) -> list[tuple[str, str]]:
    """经连接池拉取 ``(full_code, name)`` 列表（同步 TCP 隔离在池内）。"""
    return await pool.run_sync(list_a_share_stocks)


async def sync_symbols_from_pairs(pairs: list[tuple[str, str]]) -> dict[str, int]:
    """将代码表写入 ``symbol``，返回 ``total`` / ``updated``。"""
    if not pairs:
        return {"total": 0, "updated": 0}

    symbols: list[Symbol] = []
    for full_code, raw_name in pairs:
        fc = full_code.strip().lower()
        try:
            market, code = split_full_code(fc)
        except ValueError:
            continue
        name = sanitize_stock_name(raw_name, fc)
        symbols.append(Symbol(code=code, market=market, name=name, asset_type="stock"))

    if not symbols:
        return {"total": 0, "updated": 0}

    async with pg_session() as ses:
        updated = await SymbolRepo(ses).bulk_upsert(symbols)
        await ses.commit()

    logger.info("symbol_sync_done", extra={"total": len(symbols), "updated": updated})
    return {"total": len(symbols), "updated": updated}


async def sync_symbols_from_tdx(*, pool: TdxConnectionPool) -> dict[str, int]:
    """从 TDX 拉取全 A 股列表并 upsert 至 ``symbol``。"""
    pairs = await fetch_a_share_pairs(pool=pool)
    return await sync_symbols_from_pairs(pairs)
