"""回测任务用例。"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import structlog
from iquant_backtest_engine import bars_from_market, run_behavior_backtest
from iquant_domain.errors import NotFoundError, ValidationError
from iquant_domain.market import KlinePeriod
from iquant_market_service.usecases.query_bars import query_bars
from iquant_strategy_service.db import pg_session as strategy_pg_session
from ..db import pg_session
from ..models import BacktestReportORM, BacktestTaskORM
from ..repositories import backtest_repo as repo
from .schemas import (
    BacktestCreateIn,
    BacktestReportOut,
    BacktestTaskOut,
    BacktestTaskSummaryOut,
)

log = structlog.get_logger(__name__)


def _report_out(row: BacktestReportORM) -> BacktestReportOut:
    return BacktestReportOut(
        id=row.id,
        summary=dict(row.summary_json),
        data_window=dict(row.data_window_json),
        warnings=list(row.warnings_json),
        equity_curve=list(row.equity_curve_json),
        created_at=row.created_at,
    )


def _task_out(row: BacktestTaskORM) -> BacktestTaskOut:
    return BacktestTaskOut(
        id=row.id,
        strategy_version_id=row.strategy_version_id,
        full_code=row.full_code,
        period=row.period,
        status=row.status,
        error_message=row.error_message,
        created_at=row.created_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
        report=_report_out(row.report) if row.report is not None else None,
    )


def _summary_out(row: BacktestTaskORM) -> BacktestTaskSummaryOut:
    name: str | None = None
    ret: str | None = None
    if row.report is not None:
        name = str(row.report.summary_json.get("strategy_name"))
        ret = str(row.report.summary_json.get("total_return"))
    return BacktestTaskSummaryOut(
        id=row.id,
        strategy_version_id=row.strategy_version_id,
        full_code=row.full_code,
        period=row.period,
        status=row.status,
        strategy_name=name,
        total_return=ret,
        created_at=row.created_at,
        finished_at=row.finished_at,
    )


async def _load_confirmed_dsl(
    *, admin_user_id: int, strategy_version_id: UUID
) -> dict[str, object]:
    from sqlalchemy import select
    from iquant_strategy_service.models import BehaviorStrategyORM, BehaviorStrategyVersionORM

    async with strategy_pg_session() as s:
        stmt = (
            select(BehaviorStrategyVersionORM)
            .join(BehaviorStrategyORM)
            .where(
                BehaviorStrategyVersionORM.id == strategy_version_id,
                BehaviorStrategyORM.admin_user_id == admin_user_id,
            )
        )
        row = (await s.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise NotFoundError("策略版本不存在")
        if row.status != "confirmed":
            raise ValidationError("仅已确认的行为策略 DSL 可回测")
        return dict(row.dsl_json)


async def create_backtest_task(
    *,
    admin_user_id: int,
    body: BacktestCreateIn,
    idempotency_key: str,
) -> BacktestTaskOut:
    period = (body.period or "day").strip() or "day"
    await _load_confirmed_dsl(
        admin_user_id=admin_user_id, strategy_version_id=body.strategy_version_id
    )

    params = {
        "initial_cash": body.initial_cash or "1000000",
    }

    async with pg_session() as s:
        hit = await repo.find_task_by_idempotency(
            s, admin_user_id=admin_user_id, idempotency_key=idempotency_key
        )
        if hit is not None:
            await s.refresh(hit, ["report"])
            return _task_out(hit)

    row = BacktestTaskORM(
        admin_user_id=admin_user_id,
        strategy_version_id=body.strategy_version_id,
        full_code=body.full_code.strip(),
        period=period,
        params_json=params,
        status="queued",
        idempotency_key=idempotency_key,
    )
    async with pg_session() as s:
        s.add(row)
        await s.commit()
        await s.refresh(row, ["report"])

    log.info("backtest_task_created", task_id=str(row.id))
    return _task_out(row)


async def execute_backtest_task(*, task_id: UUID) -> None:
    """Worker 执行：跑引擎并写入报告。"""
    async with pg_session() as s:
        row = await repo.get_task_by_id(s, task_id=task_id)
        if row is None:
            raise NotFoundError("回测任务不存在")
        if row.status in ("succeeded", "failed"):
            return
        row.status = "running"
        row.started_at = datetime.now(tz=UTC)
        await s.commit()

    try:
        assert row.admin_user_id is not None
        dsl = await _load_confirmed_dsl(
            admin_user_id=row.admin_user_id,
            strategy_version_id=row.strategy_version_id,
        )
        kp = KlinePeriod(row.period)
        end = datetime.now(tz=UTC)
        start = end - timedelta(days=365)
        result = await query_bars(
            full_code=task_row.full_code,
            period=kp,
            start=start,
            end=end,
            limit=5000,
        )
        bars = bars_from_market(list(result.bars))
        cash = float(Decimal(str(task_row.params_json.get("initial_cash", "1000000"))))
        bt = run_behavior_backtest(dsl_doc=dsl, bars=bars, initial_cash=cash)

        async with pg_session() as s2:
            task = await repo.get_task_by_id(s2, task_id=task_id)
            assert task is not None
            report = BacktestReportORM(
                task_id=task.id,
                summary_json=bt.summary,
                data_window_json=bt.data_window,
                warnings_json=bt.warnings,
                equity_curve_json=bt.equity_curve,
            )
            s2.add(report)
            task.status = "succeeded"
            task.finished_at = datetime.now(tz=UTC)
            await s2.commit()
        log.info("backtest_task_succeeded", task_id=str(task_id))
    except Exception as e:
        log.exception("backtest_task_failed", task_id=str(task_id))
        async with pg_session() as s3:
            task = await repo.get_task_by_id(s3, task_id=task_id)
            if task is not None:
                task.status = "failed"
                task.error_message = str(e)[:2000]
                task.finished_at = datetime.now(tz=UTC)
                await s3.commit()
        raise


async def get_backtest_task(*, admin_user_id: int, task_id: UUID) -> BacktestTaskOut:
    async with pg_session() as s:
        row = await repo.get_task_for_admin(
            s, task_id=task_id, admin_user_id=admin_user_id
        )
        if row is None:
            raise NotFoundError("回测任务不存在")
        return _task_out(row)


async def list_backtest_tasks(
    *, admin_user_id: int, limit: int, offset: int
) -> tuple[list[BacktestTaskSummaryOut], int]:
    async with pg_session() as s:
        rows, total = await repo.list_tasks_for_admin(
            s, admin_user_id=admin_user_id, limit=limit, offset=offset
        )
        return [_summary_out(r) for r in rows], total
