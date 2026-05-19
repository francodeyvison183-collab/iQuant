"""策略仓储。"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import BehaviorStrategyORM, BehaviorStrategyVersionORM


async def find_by_idempotency(
    s: AsyncSession, *, admin_user_id: int, idempotency_key: str
) -> BehaviorStrategyORM | None:
    stmt = select(BehaviorStrategyORM).where(
        BehaviorStrategyORM.admin_user_id == admin_user_id,
        BehaviorStrategyORM.idempotency_key == idempotency_key,
    )
    return (await s.execute(stmt)).scalar_one_or_none()


async def get_strategy_for_admin(
    s: AsyncSession, *, strategy_id: uuid.UUID, admin_user_id: int
) -> BehaviorStrategyORM | None:
    stmt = (
        select(BehaviorStrategyORM)
        .options(selectinload(BehaviorStrategyORM.versions))
        .where(
            BehaviorStrategyORM.id == strategy_id,
            BehaviorStrategyORM.admin_user_id == admin_user_id,
        )
    )
    return (await s.execute(stmt)).scalar_one_or_none()


async def list_strategies_for_admin(
    s: AsyncSession, *, admin_user_id: int, limit: int, offset: int
) -> tuple[list[BehaviorStrategyORM], int]:
    filt = BehaviorStrategyORM.admin_user_id == admin_user_id
    total = int((await s.execute(select(func.count()).select_from(BehaviorStrategyORM).where(filt))).scalar_one())
    stmt = (
        select(BehaviorStrategyORM)
        .where(filt)
        .order_by(BehaviorStrategyORM.created_at.desc())
        .offset(offset)
        .limit(limit)
        .options(selectinload(BehaviorStrategyORM.versions))
    )
    return list((await s.execute(stmt)).scalars().all()), total


async def get_version_for_strategy(
    s: AsyncSession,
    *,
    strategy_id: uuid.UUID,
    version_id: uuid.UUID,
) -> BehaviorStrategyVersionORM | None:
    stmt = select(BehaviorStrategyVersionORM).where(
        BehaviorStrategyVersionORM.strategy_id == strategy_id,
        BehaviorStrategyVersionORM.id == version_id,
    )
    return (await s.execute(stmt)).scalar_one_or_none()
