"""行为策略用例：生成、查询、确认。"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy.exc import IntegrityError

from iquant_blind_replay_service.db import pg_session as blind_pg_session
from iquant_blind_replay_service.repositories import blind_consistency_repo
from iquant_blind_replay_service.repositories import blind_session_repo
from iquant_blind_replay_service.usecases.consistency_profile import SessionActionSample
from iquant_domain.errors import NotFoundError, ValidationError

from ..config import get_strategy_settings
from ..db import pg_session
from ..models import BehaviorStrategyORM, BehaviorStrategyVersionORM
from ..repositories import strategy_repo as repo
from .generate_from_blind import generate_candidates_from_blind
from .schemas import (
    StrategyGenerateIn,
    StrategyOut,
    StrategySummaryOut,
    StrategyVersionOut,
)

log = structlog.get_logger(__name__)


def _version_out(v: BehaviorStrategyVersionORM) -> StrategyVersionOut:
    return StrategyVersionOut(
        id=v.id,
        version_no=v.version_no,
        status=v.status,
        dsl=dict(v.dsl_json),
        rules_summary=list(v.rules_summary_json),
        rank_score=str(v.rank_score),
        is_selected=v.is_selected,
        created_at=v.created_at,
        confirmed_at=v.confirmed_at,
    )


def _strategy_out(row: BehaviorStrategyORM) -> StrategyOut:
    versions = sorted(row.versions, key=lambda x: x.version_no)
    return StrategyOut(
        id=row.id,
        name=row.name,
        status=row.status,
        source=row.source,
        period=row.period,
        consistency_report_id=row.consistency_report_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        versions=[_version_out(v) for v in versions],
    )


def _summary_out(row: BehaviorStrategyORM) -> StrategySummaryOut:
    confirmed = next((v for v in row.versions if v.status == "confirmed"), None)
    return StrategySummaryOut(
        id=row.id,
        name=row.name,
        status=row.status,
        period=row.period,
        version_count=len(row.versions),
        confirmed_version_id=confirmed.id if confirmed else None,
        created_at=row.created_at,
    )


async def generate_from_blind(
    *,
    admin_user_id: int,
    body: StrategyGenerateIn,
    idempotency_key: str,
) -> StrategyOut:
    cfg = get_strategy_settings()
    period = (body.period or "day").strip() or "day"

    async with pg_session() as s:
        hit = await repo.find_by_idempotency(
            s, admin_user_id=admin_user_id, idempotency_key=idempotency_key
        )
        if hit is not None:
            await s.refresh(hit, ["versions"])
            return _strategy_out(hit)

    async with blind_pg_session() as bs:
        if body.consistency_report_id:
            report = await blind_consistency_repo.get_report_for_admin(
                bs, report_id=body.consistency_report_id, admin_user_id=admin_user_id
            )
        else:
            report = await blind_consistency_repo.get_latest_report(
                bs, admin_user_id=admin_user_id, period=period
            )
        if report is None:
            raise ValidationError("请先生成盲测一致性报告")
        if not report.ready_for_strategy:
            raise ValidationError("一致性未达阈值，请继续盲测训练后再生成策略")

        sessions = await blind_session_repo.list_finished_sessions_with_actions(
            bs, admin_user_id=admin_user_id, period=period
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

    if len(samples) < 1:
        raise ValidationError("无已完成盲测样本，无法生成策略")

    drafts = generate_candidates_from_blind(
        samples=samples,
        period=period,
        session_count=len(samples),
        max_candidates=cfg.max_candidates,
    )
    primary_name = drafts[0].name if drafts else "行为策略草案"

    row = BehaviorStrategyORM(
        admin_user_id=admin_user_id,
        name=primary_name,
        status="draft",
        source="blind_replay",
        consistency_report_id=report.id,
        period=period,
        idempotency_key=idempotency_key,
    )
    async with pg_session() as s:
        s.add(row)
        try:
            await s.flush()
            for i, d in enumerate(drafts, start=1):
                s.add(
                    BehaviorStrategyVersionORM(
                        strategy_id=row.id,
                        version_no=i,
                        status="draft",
                        dsl_json=d.dsl.model_dump(mode="json"),
                        rules_summary_json=d.rules_summary,
                        rank_score=d.rank_score,
                        is_selected=i == 1,
                    )
                )
            await s.commit()
        except IntegrityError:
            await s.rollback()
            async with pg_session() as s2:
                hit = await repo.find_by_idempotency(
                    s2, admin_user_id=admin_user_id, idempotency_key=idempotency_key
                )
                if hit is None:
                    raise
                await s2.refresh(hit, ["versions"])
                return _strategy_out(hit)

    log.info("behavior_strategy_generated", strategy_id=str(row.id), candidates=len(drafts))
    async with pg_session() as s3:
        fresh = await repo.get_strategy_for_admin(
            s3, strategy_id=row.id, admin_user_id=admin_user_id
        )
        assert fresh is not None
        return _strategy_out(fresh)


async def get_strategy(*, admin_user_id: int, strategy_id: UUID) -> StrategyOut:
    async with pg_session() as s:
        row = await repo.get_strategy_for_admin(
            s, strategy_id=strategy_id, admin_user_id=admin_user_id
        )
        if row is None:
            raise NotFoundError("策略不存在")
        return _strategy_out(row)


async def list_strategies(
    *, admin_user_id: int, limit: int, offset: int
) -> tuple[list[StrategySummaryOut], int]:
    async with pg_session() as s:
        rows, total = await repo.list_strategies_for_admin(
            s, admin_user_id=admin_user_id, limit=limit, offset=offset
        )
        return [_summary_out(r) for r in rows], total


async def confirm_strategy_version(
    *,
    admin_user_id: int,
    strategy_id: UUID,
    version_id: UUID,
) -> StrategyOut:
    async with pg_session() as s:
        row = await repo.get_strategy_for_admin(
            s, strategy_id=strategy_id, admin_user_id=admin_user_id
        )
        if row is None:
            raise NotFoundError("策略不存在")
        ver = await repo.get_version_for_strategy(
            s, strategy_id=strategy_id, version_id=version_id
        )
        if ver is None:
            raise NotFoundError("策略版本不存在")
        if ver.status == "confirmed":
            return _strategy_out(row)

        now = datetime.now(tz=UTC)
        for v in row.versions:
            v.is_selected = v.id == version_id
            if v.id == version_id:
                v.status = "confirmed"
                v.confirmed_at = now
            elif v.status == "draft":
                v.is_selected = False

        row.status = "confirmed"
        row.name = str(ver.dsl_json.get("name", row.name))
        await s.commit()
        await s.refresh(row, ["versions"])
        log.info(
            "behavior_strategy_confirmed",
            strategy_id=str(strategy_id),
            version_id=str(version_id),
        )
        return _strategy_out(row)
