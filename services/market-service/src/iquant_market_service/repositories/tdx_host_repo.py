"""TDX 主站仓储。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from iquant_market_data.tdx.host_manager import DEFAULT_HOSTS, TdxHost

from ..models import TdxHostORM


class TdxHostRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def seed_defaults(self) -> None:
        """首次启动时把内置默认主站写入数据库。"""
        for h in DEFAULT_HOSTS:
            stmt = (
                pg_insert(TdxHostORM)
                .values(
                    ip=h["ip"],
                    port=h["port"],
                    name=h["name"],
                    is_builtin=True,
                )
                .on_conflict_do_nothing(index_elements=[TdxHostORM.ip, TdxHostORM.port])
            )
            await self.s.execute(stmt)

    async def list_all(self) -> list[TdxHostORM]:
        rows = (
            await self.s.execute(select(TdxHostORM).order_by(TdxHostORM.speed_ms))
        ).scalars().all()
        return list(rows)

    async def add(self, *, ip: str, port: int, name: str) -> TdxHostORM:
        row = TdxHostORM(ip=ip, port=port, name=name or f"{ip}:{port}", is_builtin=False)
        self.s.add(row)
        await self.s.flush()
        return row

    async def remove(self, host_id: int) -> bool:
        row = await self.s.get(TdxHostORM, host_id)
        if row is None or row.is_builtin:
            return False
        await self.s.delete(row)
        return True

    async def update_test_result(
        self,
        *,
        ip: str,
        port: int,
        status: str,
        speed_ms: int,
    ) -> None:
        now = datetime.now()
        stmt = select(TdxHostORM).where(TdxHostORM.ip == ip, TdxHostORM.port == port)
        row = (await self.s.execute(stmt)).scalar_one_or_none()
        if row is None:
            return
        row.status = status
        row.speed_ms = speed_ms
        row.last_tested = now
        if status == "ok":
            row.fail_since = None
        elif row.fail_since is None:
            row.fail_since = now

    async def to_tdx_hosts(self) -> list[TdxHost]:
        rows = await self.list_all()
        out: list[TdxHost] = []
        for r in rows:
            out.append(
                TdxHost(
                    ip=r.ip,
                    port=r.port,
                    name=r.name,
                    status=r.status,
                    speed_ms=r.speed_ms,
                    last_tested=r.last_tested.strftime("%Y-%m-%d %H:%M:%S") if r.last_tested else None,
                    fail_since=r.fail_since.strftime("%Y-%m-%d %H:%M:%S") if r.fail_since else None,
                )
            )
        return out
