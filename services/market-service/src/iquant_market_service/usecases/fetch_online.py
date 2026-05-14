"""在线 TDX 行情拉取与补数用例。"""
from __future__ import annotations

import logging

from iquant_domain.market import KlinePeriod
from iquant_market_data.tdx.host_manager import TdxHostManager
from iquant_market_data.tdx.pool import TdxConnectionPool
from iquant_market_data.tdx.source import TdxMarketDataSource

from ..config import get_market_settings
from ..db import ts_session
from ..repositories.market_bar_repo import MarketBarRepo

logger = logging.getLogger(__name__)

_pool: TdxConnectionPool | None = None
_source: TdxMarketDataSource | None = None


def _ensure_source() -> TdxMarketDataSource:
    global _pool, _source
    if _source is None:
        s = get_market_settings()
        hm = TdxHostManager(config_path=s.tdx_hosts_config)
        hm.load()
        _pool = TdxConnectionPool(
            hm,
            max_size=s.tdx_pool_size,
            connect_timeout=s.tdx_connect_timeout,
            read_timeout=s.tdx_read_timeout,
        )
        _source = TdxMarketDataSource(_pool)
    return _source


async def fetch_and_save_online(
    *,
    full_code: str,
    period: KlinePeriod,
    max_count: int = 800,
) -> int:
    """在线拉取并落库，返回实际写入条数。"""
    src = _ensure_source()
    batch = await src.fetch_bars(full_code=full_code, period=period, limit=max_count)
    if batch.is_empty:
        return 0
    async with ts_session() as ts:
        inserted = await MarketBarRepo(ts).bulk_upsert(batch.bars, source="tdx-online")
        await ts.commit()
    return inserted
