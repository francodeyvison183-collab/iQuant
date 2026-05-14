"""TDX 行情数据源实现（在线 TCP 协议）。

实现 :class:`iquant_market_data.protocols.MarketDataSource` 协议，
供 ``services/market-service`` 在用例中按抽象使用。
"""
from __future__ import annotations

import logging
from datetime import datetime

from iquant_domain.market import KlinePeriod, MarketBarBatch, Symbol

from .pool import TdxConnectionPool

logger = logging.getLogger(__name__)


class TdxMarketDataSource:
    """基于在线 TDX 协议的行情数据源。"""

    name = "tdx-online"

    def __init__(self, pool: TdxConnectionPool) -> None:
        self._pool = pool

    @property
    def pool(self) -> TdxConnectionPool:
        """暴露底层连接池，供需要直接调度 ``TdxClient`` 同步方法的用例使用。"""
        return self._pool

    async def list_symbols(self) -> list[Symbol]:
        """在线列出所有标的。

        MVP 暂不实现完整的 GetSecurityList 协议解析（数据量大、协议细节多）。
        实际项目中标的清单来自本地 vipdoc 扫描结果 + 数据库 ``symbol`` 表，
        在线源仅作为补充。这里返回空列表，调用方应改走本地扫描。
        """
        return []

    async def fetch_bars(
        self,
        *,
        full_code: str,
        period: KlinePeriod,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int | None = None,
    ) -> MarketBarBatch:
        """在线拉取一段 K 线。

        TDX 协议无法按"绝对时间窗口"请求，只能按"最近 N 根"请求；
        因此 start/end 用作客户端侧过滤，limit 决定最多拉多少。
        """
        max_count = limit or 800
        batch = await self._pool.run_sync_with_retry(
            lambda c: c.fetch_bars_paged(
                full_code=full_code,
                period=period,
                max_count=max_count,
            )
        )
        if start or end:
            filtered = [
                bar
                for bar in batch.bars
                if (start is None or bar.bar_time >= start)
                and (end is None or bar.bar_time <= end)
            ]
            return MarketBarBatch(full_code=full_code, period=period, bars=filtered)
        return batch

    async def healthcheck(self) -> bool:
        try:
            await self._pool.run_sync(lambda c: c.connected or (c.connect() or True))
            return True
        except Exception as exc:  # noqa: BLE001 - 健康检查兜底
            logger.warning("tdx_source_unhealthy", extra={"error": str(exc)})
            return False
