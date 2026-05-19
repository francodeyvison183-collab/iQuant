"""回测仓储。"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import BacktestReportORM, BacktestTaskORM


async def find_task_by_idempotency(
    s: AsyncSession, *, admin_user_id: int, idempotency_key: str
) -> BacktestTaskORM | None:
    stmt = select(BacktestTaskORM).where(
        BacktestTaskORM.admin_user_id == admin_user_id,
        BacktestTaskORM.idempotency_key == idempotency_key,
    )
    return (await s.execute(stmt)).scalar_one_or_none()


async def get_task_for_admin(
    s: AsyncSession, *, task_id: uuid.UUID, admin_user_id: int
) -> BacktestTaskORM | None:
    stmt = (
        select(BacktestTaskORM)
        .options(selectinload(BacktestTaskORM.report))
        .where(
            BacktestTaskORM.id == task_id,
            BacktestTaskORM.admin_user_id == admin_user_id,
        )
    )
    return (await s.execute(stmt)).scalar_one_or_none()


async def get_task_by_id(s: AsyncSession, *, task_id: uuid.UUID) -> BacktestTaskORM | None:
    stmt = (
        select(BacktestTaskORM)
        .options(selectinload(BacktestTaskORM.report))
        .where(BacktestTaskORM.id == task_id)
    )
    return (await s.execute(stmt)).scalar_one_or_none()


async def list_tasks_for_admin(
    s: AsyncSession, *, admin_user_id: int, limit: int, offset: int
) -> tuple[list[BacktestTaskORM], int]:
    filt = BacktestTaskORM.admin_user_id == admin_user_id
    total = int((await s.execute(select(func.count()).select_from(BacktestTaskORM).where(filt))).scalar_one())
    stmt = (
        select(BacktestTaskORM)
        .where(filt)
        .order_by(BacktestTaskORM.created_at.desc())
        .offset(offset)
        .limit(limit)
        .options(selectinload(BacktestTaskORM.report))
    )
    return list((await s.execute(stmt)).scalars().all()), total
