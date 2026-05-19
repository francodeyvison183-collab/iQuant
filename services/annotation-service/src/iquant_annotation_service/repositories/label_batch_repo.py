"""标注批次仓储。"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import LabelBatchORM, LabelBatchSummaryORM, LabelPairORM, LabelQueueItemORM


async def get_batch_for_admin(
    s: AsyncSession, *, batch_id: uuid.UUID, admin_user_id: int
) -> LabelBatchORM | None:
    stmt = (
        select(LabelBatchORM)
        .options(selectinload(LabelBatchORM.items))
        .where(LabelBatchORM.id == batch_id, LabelBatchORM.admin_user_id == admin_user_id)
    )
    return (await s.execute(stmt)).scalar_one_or_none()


async def get_queue_item(
    s: AsyncSession, *, batch_id: uuid.UUID, item_id: uuid.UUID
) -> LabelQueueItemORM | None:
    stmt = select(LabelQueueItemORM).where(
        LabelQueueItemORM.batch_id == batch_id,
        LabelQueueItemORM.id == item_id,
    )
    return (await s.execute(stmt)).scalar_one_or_none()


async def count_item_statuses(
    s: AsyncSession, *, batch_id: uuid.UUID
) -> dict[str, int]:
    stmt = (
        select(LabelQueueItemORM.status, func.count())
        .where(LabelQueueItemORM.batch_id == batch_id)
        .group_by(LabelQueueItemORM.status)
    )
    rows = (await s.execute(stmt)).all()
    return {str(status): int(cnt) for status, cnt in rows}


async def mark_batch_completed(s: AsyncSession, *, batch: LabelBatchORM) -> None:
    batch.status = "completed"
    batch.completed_at = datetime.now(tz=UTC)


async def session_pair_count(s: AsyncSession, *, session_id: uuid.UUID) -> int:
    pair_stmt = select(func.count()).select_from(LabelPairORM).where(
        LabelPairORM.session_id == session_id
    )
    return int((await s.execute(pair_stmt)).scalar_one())


async def list_batches_for_admin(
    s: AsyncSession, *, admin_user_id: int, limit: int, offset: int
) -> tuple[list[LabelBatchORM], int]:
    filt = LabelBatchORM.admin_user_id == admin_user_id
    cnt_stmt = select(func.count()).select_from(LabelBatchORM).where(filt)
    total = int((await s.execute(cnt_stmt)).scalar_one())
    stmt = (
        select(LabelBatchORM)
        .where(filt)
        .order_by(LabelBatchORM.created_at.desc())
        .offset(offset)
        .limit(limit)
        .options(selectinload(LabelBatchORM.items))
    )
    rows = list((await s.execute(stmt)).scalars().all())
    return rows, total


async def get_summary(s: AsyncSession, *, batch_id: uuid.UUID) -> LabelBatchSummaryORM | None:
    stmt = select(LabelBatchSummaryORM).where(LabelBatchSummaryORM.batch_id == batch_id)
    return (await s.execute(stmt)).scalar_one_or_none()


async def upsert_summary(
    s: AsyncSession,
    *,
    batch_id: uuid.UUID,
    stats_json: dict,
    profile_draft: str,
    insights_json: list,
    correction_options_json: list,
    user_corrections_json: list[str] | None = None,
) -> LabelBatchSummaryORM:
    row = await get_summary(s, batch_id=batch_id)
    if row is None:
        row = LabelBatchSummaryORM(
            batch_id=batch_id,
            stats_json=stats_json,
            profile_draft=profile_draft,
            insights_json=insights_json,
            correction_options_json=correction_options_json,
            user_corrections_json=user_corrections_json or [],
        )
        s.add(row)
    else:
        row.stats_json = stats_json
        row.profile_draft = profile_draft
        row.insights_json = insights_json
        row.correction_options_json = correction_options_json
        if user_corrections_json is not None:
            row.user_corrections_json = user_corrections_json
    await s.flush()
    return row


async def load_pair_samples_for_batch(
    s: AsyncSession, *, batch_id: uuid.UUID
) -> list[tuple[LabelPairORM, str]]:
    """返回 (pair, full_code) 列表，仅 completed 队列项。"""
    stmt = (
        select(LabelPairORM, LabelQueueItemORM.full_code)
        .join(
            LabelQueueItemORM,
            LabelQueueItemORM.session_id == LabelPairORM.session_id,
        )
        .where(
            LabelQueueItemORM.batch_id == batch_id,
            LabelQueueItemORM.status == "completed",
        )
    )
    rows = (await s.execute(stmt)).all()
    return [(pair, full_code) for pair, full_code in rows]


async def total_pairs_in_batch(s: AsyncSession, *, batch_id: uuid.UUID) -> int:
    stmt = (
        select(func.count())
        .select_from(LabelPairORM)
        .join(LabelQueueItemORM, LabelQueueItemORM.session_id == LabelPairORM.session_id)
        .where(LabelQueueItemORM.batch_id == batch_id)
    )
    return int((await s.execute(stmt)).scalar_one())
