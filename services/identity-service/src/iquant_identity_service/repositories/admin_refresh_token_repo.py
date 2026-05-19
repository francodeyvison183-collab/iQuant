"""Refresh token 仓储。"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AdminRefreshTokenORM


class AdminRefreshTokenRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def create(
        self,
        *,
        admin_user_id: int,
        token_hash: str,
        expires_at: datetime,
        ip: str,
        user_agent: str,
    ) -> AdminRefreshTokenORM:
        row = AdminRefreshTokenORM(
            admin_user_id=admin_user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            ip=ip,
            user_agent=user_agent,
        )
        self.s.add(row)
        await self.s.flush()
        return row

    async def get_valid(self, token_hash: str) -> AdminRefreshTokenORM | None:
        now = datetime.now(tz=UTC)
        return (
            await self.s.execute(
                select(AdminRefreshTokenORM).where(
                    AdminRefreshTokenORM.token_hash == token_hash,
                    AdminRefreshTokenORM.revoked_at.is_(None),
                    AdminRefreshTokenORM.expires_at > now,
                )
            )
        ).scalar_one_or_none()

    async def revoke(self, token_hash: str) -> None:
        row = (
            await self.s.execute(
                select(AdminRefreshTokenORM).where(AdminRefreshTokenORM.token_hash == token_hash)
            )
        ).scalar_one_or_none()
        if row is None or row.revoked_at is not None:
            return
        row.revoked_at = datetime.now(tz=UTC)
        await self.s.flush()
