"""跨轮一致性评估用例（迭代 1b）。"""
from __future__ import annotations

from uuid import UUID

import structlog

from iquant_domain.errors import NotFoundError, ValidationError

from ..config import get_blind_replay_settings
from ..db import pg_session
from ..repositories import blind_consistency_repo as report_repo
from ..repositories import blind_session_repo as session_repo
from .consistency_profile import (
    CORRECTION_OPTION_IDS,
    SessionActionSample,
    build_consistency_profile,
)
from .schemas import BlindConsistencyPatchIn, BlindConsistencyReportOut

log = structlog.get_logger(__name__)


def _report_to_out(row) -> BlindConsistencyReportOut:  # type: ignore[no-untyped-def]
    return BlindConsistencyReportOut(
        id=row.id,
        period=row.period,
        session_count=row.session_count,
        scores=dict(row.scores_json),
        profile_draft=row.profile_draft,
        insights=list(row.insights_json),
        correction_options=list(row.correction_options_json),
        user_corrections=list(row.user_corrections_json),
        ready_for_strategy=row.ready_for_strategy,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def evaluate_consistency_report(
    *,
    admin_user_id: int,
    period: str | None = None,
    regenerate: bool = False,
) -> BlindConsistencyReportOut:
    cfg = get_blind_replay_settings()
    p = (period or "day").strip() or "day"

    async with pg_session() as s:
        if not regenerate:
            existing = await report_repo.get_latest_report(
                s, admin_user_id=admin_user_id, period=p
            )
            if existing is not None:
                return _report_to_out(existing)

        sessions = await session_repo.list_finished_sessions_with_actions(
            s, admin_user_id=admin_user_id, period=p
        )
        samples = [
            SessionActionSample(
                session_id=sess.id,
                full_code=sess.full_code,
                actions=[
                    (a.bar_time, a.user_action, dict(a.features_snapshot))
                    for a in sorted(sess.actions, key=lambda x: x.bar_time)
                ],
            )
            for sess in sessions
        ]
        profile = build_consistency_profile(
            samples=samples,
            session_count=len(sessions),
            min_sessions=cfg.consistency_min_sessions,
            ready_threshold=cfg.consistency_ready_threshold,
        )
        row = await report_repo.insert_report(
            s,
            admin_user_id=admin_user_id,
            period=p,
            session_count=len(sessions),
            scores_json=profile.scores,
            profile_draft=profile.profile_draft,
            insights_json=profile.insights,
            correction_options_json=profile.correction_options,
            ready_for_strategy=profile.ready_for_strategy,
        )
        await s.commit()
        await s.refresh(row)
        log.info(
            "blind_consistency_report_created",
            report_id=str(row.id),
            session_count=len(sessions),
        )
        return _report_to_out(row)


async def get_consistency_report(
    *,
    admin_user_id: int,
    period: str | None = None,
) -> BlindConsistencyReportOut:
    p = period.strip() if period else None
    async with pg_session() as s:
        row = await report_repo.get_latest_report(
            s, admin_user_id=admin_user_id, period=p
        )
        if row is None:
            raise NotFoundError("尚无一致性报告，请先完成至少一轮盲测并生成报告")
        return _report_to_out(row)


async def patch_consistency_corrections(
    *,
    admin_user_id: int,
    report_id: UUID,
    body: BlindConsistencyPatchIn,
) -> BlindConsistencyReportOut:
    for cid in body.user_corrections:
        if cid not in CORRECTION_OPTION_IDS:
            raise ValidationError(f"未知修正项: {cid}")

    async with pg_session() as s:
        row = await report_repo.get_report_for_admin(
            s, report_id=report_id, admin_user_id=admin_user_id
        )
        if row is None:
            raise NotFoundError("一致性报告不存在")
        row.user_corrections_json = list(body.user_corrections)
        await s.commit()
        await s.refresh(row)
        return _report_to_out(row)
