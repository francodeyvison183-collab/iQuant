"""盲测会话仓储。"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import BlindActionORM, BlindSessionORM


async def find_session_by_idempotency(
    s: AsyncSession, *, admin_user_id: int, idempotency_key: str
) -> BlindSessionORM | None:
    stmt = select(BlindSessionORM).where(
        BlindSessionORM.admin_user_id == admin_user_id,
        BlindSessionORM.idempotency_key == idempotency_key,
    )
    return (await s.execute(stmt)).scalar_one_or_none()


async def get_session_for_admin(
    s: AsyncSession, *, session_id: uuid.UUID, admin_user_id: int
) -> BlindSessionORM | None:
    stmt = (
        select(BlindSessionORM)
        .options(selectinload(BlindSessionORM.actions))
        .where(
            BlindSessionORM.id == session_id,
            BlindSessionORM.admin_user_id == admin_user_id,
        )
    )
    return (await s.execute(stmt)).scalar_one_or_none()


async def list_sessions_for_admin(
    s: AsyncSession, *, admin_user_id: int, limit: int, offset: int, status: str | None
) -> tuple[list[BlindSessionORM], int]:
    filt = BlindSessionORM.admin_user_id == admin_user_id
    if status:
        filt = filt & (BlindSessionORM.status == status)
    cnt_stmt = select(func.count()).select_from(BlindSessionORM).where(filt)
    total = int((await s.execute(cnt_stmt)).scalar_one())
    stmt = (
        select(BlindSessionORM)
        .where(filt)
        .order_by(BlindSessionORM.created_at.desc())
        .offset(offset)
        .limit(limit)
        .options(selectinload(BlindSessionORM.actions))
    )
    rows = list((await s.execute(stmt)).scalars().all())
    return rows, total


async def count_finished_sessions(
    s: AsyncSession, *, admin_user_id: int, period: str | None
) -> int:
    filt = (BlindSessionORM.admin_user_id == admin_user_id) & (
        BlindSessionORM.status == "finished"
    )
    if period:
        filt = filt & (BlindSessionORM.period == period)
    stmt = select(func.count()).select_from(BlindSessionORM).where(filt)
    return int((await s.execute(stmt)).scalar_one())


async def list_finished_sessions_with_actions(
    s: AsyncSession, *, admin_user_id: int, period: str | None, limit: int = 50
) -> list[BlindSessionORM]:
    filt = (BlindSessionORM.admin_user_id == admin_user_id) & (
        BlindSessionORM.status == "finished"
    )
    if period:
        filt = filt & (BlindSessionORM.period == period)
    stmt = (
        select(BlindSessionORM)
        .where(filt)
        .order_by(BlindSessionORM.completed_at.desc())
        .limit(limit)
        .options(selectinload(BlindSessionORM.actions))
    )
    return list((await s.execute(stmt)).scalars().all())


async def has_action_at_bar(
    s: AsyncSession, *, session_id: uuid.UUID, bar_time: datetime
) -> bool:
    stmt = select(BlindActionORM.id).where(
        BlindActionORM.session_id == session_id,
        BlindActionORM.bar_time == bar_time,
    )
    return (await s.execute(stmt)).scalar_one_or_none() is not None


async def list_used_full_codes_in_range(
    s: AsyncSession,
    *,
    admin_user_id: int,
    range_start: datetime,
    range_end: datetime,
) -> set[str]:
    """同一用户在完全相同 ``[range_start, range_end]`` 已建会话过的标的集合。"""
    stmt = select(BlindSessionORM.full_code).where(
        BlindSessionORM.admin_user_id == admin_user_id,
        BlindSessionORM.range_start == range_start,
        BlindSessionORM.range_end == range_end,
    )
    return {row[0] for row in (await s.execute(stmt)).all()}


async def list_open_round_sessions(
    s: AsyncSession, *, admin_user_id: int
) -> list[BlindSessionORM]:
    """当前用户"开放轮次"的所有会话（在最后一次 finished/abandoned 之后）。

    返回按 ``created_at`` 升序，可能为空（无开放轮）。
    """
    last_term_stmt = select(func.max(BlindSessionORM.created_at)).where(
        BlindSessionORM.admin_user_id == admin_user_id,
        BlindSessionORM.status.in_(["finished", "abandoned"]),
    )
    last_term_at: datetime | None = (await s.execute(last_term_stmt)).scalar_one_or_none()
    filt = (BlindSessionORM.admin_user_id == admin_user_id) & (
        BlindSessionORM.status.in_(["active", "switched"])
    )
    if last_term_at is not None:
        filt = filt & (BlindSessionORM.created_at > last_term_at)
    stmt = (
        select(BlindSessionORM)
        .where(filt)
        .order_by(BlindSessionORM.created_at.asc())
        .options(selectinload(BlindSessionORM.actions))
    )
    return list((await s.execute(stmt)).scalars().all())


async def list_all_sessions_for_admin(
    s: AsyncSession, *, admin_user_id: int, limit: int = 500
) -> list[BlindSessionORM]:
    """拉取该用户全部会话用于轮次推导（默认按 created_at 升序）。"""
    stmt = (
        select(BlindSessionORM)
        .where(BlindSessionORM.admin_user_id == admin_user_id)
        .order_by(BlindSessionORM.created_at.asc())
        .limit(limit)
        .options(selectinload(BlindSessionORM.actions))
    )
    return list((await s.execute(stmt)).scalars().all())
