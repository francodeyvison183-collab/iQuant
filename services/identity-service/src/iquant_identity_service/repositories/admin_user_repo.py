"""管理员账号仓储。"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AdminUserORM


class AdminUserRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def count(self) -> int:
        return int((await self.s.execute(select(func.count()).select_from(AdminUserORM))).scalar_one())

    async def get_by_username(self, username: str) -> AdminUserORM | None:
        return (
            await self.s.execute(select(AdminUserORM).where(AdminUserORM.username == username))
        ).scalar_one_or_none()

    async def get_by_id(self, admin_id: int) -> AdminUserORM | None:
        return (
            await self.s.execute(select(AdminUserORM).where(AdminUserORM.id == admin_id))
        ).scalar_one_or_none()

    async def create(
        self,
        *,
        username: str,
        password_hash: str,
        display_name: str,
    ) -> AdminUserORM:
        row = AdminUserORM(
            username=username,
            password_hash=password_hash,
            display_name=display_name or username,
            is_active=True,
        )
        self.s.add(row)
        await self.s.flush()
        return row

    async def update_login(self, admin_id: int) -> None:
        row = await self.get_by_id(admin_id)
        if row is None:
            return
        row.last_login_at = datetime.now(tz=UTC)
        await self.s.flush()

    async def update_password(self, admin_id: int, password_hash: str) -> None:
        row = await self.get_by_id(admin_id)
        if row is None:
            return
        row.password_hash = password_hash
        row.password_changed_at = datetime.now(tz=UTC)
        await self.s.flush()
