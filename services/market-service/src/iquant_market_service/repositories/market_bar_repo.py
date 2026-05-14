"""市场 K 线仓储（TimescaleDB）。"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import desc, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from iquant_domain.market import KlinePeriod, MarketBar

from ..models import MarketBarORM


class MarketBarRepo:
    """K 线读写。

    写：批量 ``ON CONFLICT DO NOTHING``，保证幂等导入。
    读：按 ``(full_code, period, bar_time)`` 范围扫描。
    """

    BATCH_SIZE = 1000

    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def bulk_upsert(self, bars: list[MarketBar], *, source: str) -> int:
        """批量插入；已存在的 (full_code, period, bar_time) 跳过。返回实际写入条数。"""
        if not bars:
            return 0
        now = datetime.now(tz=timezone.utc)
        rows = [
            {
                "full_code": b.full_code,
                "period": b.period.value,
                "bar_time": b.bar_time if b.bar_time.tzinfo else b.bar_time.replace(tzinfo=timezone.utc),
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "volume": b.volume,
                "amount": b.amount,
                "adj_factor": b.adj_factor,
                "source": source,
                "ingested_at": now,
            }
            for b in bars
        ]
        inserted = 0
        for start in range(0, len(rows), self.BATCH_SIZE):
            chunk = rows[start : start + self.BATCH_SIZE]
            stmt = pg_insert(MarketBarORM).values(chunk).on_conflict_do_nothing(
                index_elements=[MarketBarORM.full_code, MarketBarORM.period, MarketBarORM.bar_time]
            )
            result = await self.s.execute(stmt)
            # rowcount: 实际写入数（PG 支持），失败回退用 len(chunk)
            inserted += int(result.rowcount or len(chunk))
        return inserted

    async def get_last_bar_time(
        self, *, full_code: str, period: KlinePeriod
    ) -> datetime | None:
        stmt = (
            select(MarketBarORM.bar_time)
            .where(MarketBarORM.full_code == full_code)
            .where(MarketBarORM.period == period.value)
            .order_by(desc(MarketBarORM.bar_time))
            .limit(1)
        )
        return (await self.s.execute(stmt)).scalar_one_or_none()

    async def query_bars(
        self,
        *,
        full_code: str,
        period: KlinePeriod,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 500,
    ) -> list[MarketBarORM]:
        q = (
            select(MarketBarORM)
            .where(MarketBarORM.full_code == full_code)
            .where(MarketBarORM.period == period.value)
        )
        if start:
            q = q.where(MarketBarORM.bar_time >= start)
        if end:
            q = q.where(MarketBarORM.bar_time <= end)
        q = q.order_by(MarketBarORM.bar_time).limit(limit)
        return list((await self.s.execute(q)).scalars().all())

    async def count_by_symbol(
        self, *, full_code: str, period: KlinePeriod | None = None
    ) -> int:
        q = select(func.count()).select_from(MarketBarORM).where(
            MarketBarORM.full_code == full_code
        )
        if period:
            q = q.where(MarketBarORM.period == period.value)
        return int((await self.s.execute(q)).scalar_one())

    async def coverage(
        self, *, full_code: str, period: KlinePeriod
    ) -> tuple[datetime | None, datetime | None, int]:
        """返回某标的某周期的 (min_time, max_time, count)。"""
        stmt = select(
            func.min(MarketBarORM.bar_time),
            func.max(MarketBarORM.bar_time),
            func.count(),
        ).where(
            MarketBarORM.full_code == full_code,
            MarketBarORM.period == period.value,
        )
        row = (await self.s.execute(stmt)).one()
        return row[0], row[1], int(row[2] or 0)
