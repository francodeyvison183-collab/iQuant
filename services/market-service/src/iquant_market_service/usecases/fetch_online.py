"""在线 TDX 行情拉取与补数用例。"""
from __future__ import annotations

import logging

from iquant_market_data.tdx.host_manager import TdxHostManager
from iquant_market_data.tdx.pool import TdxConnectionPool
from iquant_market_data.tdx.source import TdxMarketDataSource

from ..config import get_market_settings

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


def reload_tdx_source() -> TdxMarketDataSource:
    """丢弃进程内缓存的连接池，使批量任务重新加载主站列表。"""
    global _pool, _source
    _pool = None
    _source = None
    return _ensure_source()

