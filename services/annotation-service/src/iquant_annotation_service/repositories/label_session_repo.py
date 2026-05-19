"""标注会话仓储。"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import LabelPairORM, LabelSessionORM


async def find_session_by_idempotency(
    s: AsyncSession, *, admin_user_id: int, idempotency_key: str
) -> LabelSessionORM | None:
    stmt = select(LabelSessionORM).where(
        LabelSessionORM.admin_user_id == admin_user_id,
        LabelSessionORM.idempotency_key == idempotency_key,
    )
    return (await s.execute(stmt)).scalar_one_or_none()


async def get_session_for_admin(
    s: AsyncSession, *, session_id: uuid.UUID, admin_user_id: int
) -> LabelSessionORM | None:
    stmt = (
        select(LabelSessionORM)
        .options(selectinload(LabelSessionORM.pairs))
        .where(
            LabelSessionORM.id == session_id,
            LabelSessionORM.admin_user_id == admin_user_id,
        )
    )
    return (await s.execute(stmt)).scalar_one_or_none()


async def list_sessions_for_admin(
    s: AsyncSession, *, admin_user_id: int, limit: int, offset: int
) -> tuple[list[LabelSessionORM], int]:
    filt = LabelSessionORM.admin_user_id == admin_user_id
    cnt_stmt = select(func.count()).select_from(LabelSessionORM).where(filt)
    total = int((await s.execute(cnt_stmt)).scalar_one())
    stmt = (
        select(LabelSessionORM)
        .where(filt)
        .order_by(LabelSessionORM.created_at.desc())
        .offset(offset)
        .limit(limit)
        .options(selectinload(LabelSessionORM.pairs))
    )
    rows = list((await s.execute(stmt)).scalars().all())
    return rows, total


async def delete_session(s: AsyncSession, *, row: LabelSessionORM) -> None:
    await s.delete(row)


async def delete_pairs_for_session(s: AsyncSession, *, session_id: uuid.UUID) -> None:
    await s.execute(delete(LabelPairORM).where(LabelPairORM.session_id == session_id))


async def insert_pairs(
    s: AsyncSession, *, session_id: uuid.UUID, pairs: list[LabelPairORM]
) -> None:
    for p in pairs:
        p.session_id = session_id
        s.add(p)
