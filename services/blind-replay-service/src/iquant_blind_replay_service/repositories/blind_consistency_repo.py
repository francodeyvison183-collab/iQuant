"""一致性报告仓储。"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import BlindConsistencyReportORM


async def get_report_for_admin(
    s: AsyncSession, *, report_id: uuid.UUID, admin_user_id: int
) -> BlindConsistencyReportORM | None:
    stmt = select(BlindConsistencyReportORM).where(
        BlindConsistencyReportORM.id == report_id,
        BlindConsistencyReportORM.admin_user_id == admin_user_id,
    )
    return (await s.execute(stmt)).scalar_one_or_none()


async def get_latest_report(
    s: AsyncSession, *, admin_user_id: int, period: str | None
) -> BlindConsistencyReportORM | None:
    filt = BlindConsistencyReportORM.admin_user_id == admin_user_id
    if period:
        filt = filt & (BlindConsistencyReportORM.period == period)
    stmt = (
        select(BlindConsistencyReportORM)
        .where(filt)
        .order_by(BlindConsistencyReportORM.created_at.desc())
        .limit(1)
    )
    return (await s.execute(stmt)).scalar_one_or_none()


async def insert_report(
    s: AsyncSession,
    *,
    admin_user_id: int,
    period: str,
    session_count: int,
    scores_json: dict[str, Any],
    profile_draft: str,
    insights_json: list[Any],
    correction_options_json: list[Any],
    ready_for_strategy: bool,
) -> BlindConsistencyReportORM:
    row = BlindConsistencyReportORM(
        admin_user_id=admin_user_id,
        period=period,
        session_count=session_count,
        scores_json=scores_json,
        profile_draft=profile_draft,
        insights_json=insights_json,
        correction_options_json=correction_options_json,
        user_corrections_json=[],
        ready_for_strategy=ready_for_strategy,
    )
    s.add(row)
    await s.flush()
    return row
