"""标的仓储。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from iquant_domain.market import Market, Symbol

from ..models import SymbolORM


class SymbolRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def upsert(self, sym: Symbol) -> None:
        stmt = (
            pg_insert(SymbolORM)
            .values(
                code=sym.code,
                market=sym.market.value,
                full_code=sym.full_code,
                name=sym.name,
                asset_type=sym.asset_type,
                list_date=sym.list_date,
                delist_date=sym.delist_date,
                extra={},
            )
            .on_conflict_do_update(
                index_elements=[SymbolORM.full_code],
                set_={
                    "name": sym.name,
                    "asset_type": sym.asset_type,
                    "list_date": sym.list_date,
                    "delist_date": sym.delist_date,
                },
            )
        )
        await self.s.execute(stmt)

    async def upsert_basic(self, full_code: str, market: Market, code: str) -> None:
        """从扫描结果创建占位标的，名称由后续维护任务回填。"""
        stmt = (
            pg_insert(SymbolORM)
            .values(
                code=code,
                market=market.value,
                full_code=full_code,
                name="",
                asset_type="stock",
                extra={},
            )
            .on_conflict_do_nothing(index_elements=[SymbolORM.full_code])
        )
        await self.s.execute(stmt)

    async def list_paged(
        self,
        *,
        market: str | None = None,
        keyword: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[SymbolORM], int]:
        q = select(SymbolORM)
        c = select(func.count()).select_from(SymbolORM)
        if market:
            q = q.where(SymbolORM.market == market)
            c = c.where(SymbolORM.market == market)
        if keyword:
            kw = f"%{keyword}%"
            q = q.where((SymbolORM.code.ilike(kw)) | (SymbolORM.name.ilike(kw)))
            c = c.where((SymbolORM.code.ilike(kw)) | (SymbolORM.name.ilike(kw)))
        q = q.order_by(SymbolORM.full_code).limit(limit).offset(offset)
        rows = (await self.s.execute(q)).scalars().all()
        total = (await self.s.execute(c)).scalar_one()
        return list(rows), int(total)

    async def get_by_full_code(self, full_code: str) -> SymbolORM | None:
        return (
            await self.s.execute(select(SymbolORM).where(SymbolORM.full_code == full_code))
        ).scalar_one_or_none()
