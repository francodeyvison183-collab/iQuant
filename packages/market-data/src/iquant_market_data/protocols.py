"""行情数据源抽象协议。

业务侧（services / apps）一律通过 ``MarketDataSource`` 接口与具体数据源交互，
通达信、东方财富、本地 Parquet 等都实现这个协议，便于替换与组合。
"""
from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from iquant_domain.market import KlinePeriod, MarketBarBatch, Symbol


@runtime_checkable
class MarketDataSource(Protocol):
    """行情数据源协议。"""

    name: str

    async def list_symbols(self) -> list[Symbol]:
        """列出该数据源支持的所有标的。"""
        ...

    async def fetch_bars(
        self,
        *,
        full_code: str,
        period: KlinePeriod,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int | None = None,
    ) -> MarketBarBatch:
        """拉取一段 K 线。

        参数：
            full_code: 带市场前缀的代码，如 sh600519
            period: K 线周期
            start, end: 时间窗口（含端点）；None 表示由数据源决定默认窗口
            limit: 最多返回多少根（用于增量拉取或预览）
        """
        ...

    async def healthcheck(self) -> bool:
        """数据源健康检查。"""
        ...
