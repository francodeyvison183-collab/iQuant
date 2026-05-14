"""行情相关 Celery 任务。

任务本身只是"接收任务调用 → 委托到 service 用例 → 转发进度事件"，
真正的业务逻辑全部在 ``iquant_market_service.usecases.*``。
"""
from __future__ import annotations

import asyncio
import logging
import uuid

from celery.exceptions import SoftTimeLimitExceeded

from iquant_market_service.db import pg_session
from iquant_market_service.models import MarketImportTaskStatus, MarketImportTaskType
from iquant_market_service.progress_bus import publish
from iquant_market_service.repositories.import_task_repo import ImportTaskRepo
from iquant_market_service.usecases.batch_online_fetch import execute_batch_online_task
from iquant_market_service.usecases.import_local import execute_import_task
from iquant_market_service.usecases.manage_hosts import test_hosts

from ..celery_app import app

logger = logging.getLogger(__name__)


def _run(coro):  # type: ignore[no-untyped-def]
    """在 Celery worker 进程内运行协程：每次任务用独立 event loop。"""
    try:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    finally:
        # 防止 default executor 残留
        pass


# ─── 历史行情导入 ─────────────────────────────────────────────────────────────


@app.task(
    name="market.import_local",
    bind=True,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=5,
    retry_backoff_max=120,
    retry_jitter=True,
    max_retries=3,
    soft_time_limit=3600,
    time_limit=3900,
)
def task_import_local(self, task_id: str | None = None) -> dict:  # type: ignore[no-untyped-def]
    """执行历史行情导入任务（增量或全量）。

    - 由 API 投递：``task_id`` 一般等于 ``self.request.id``。
    - 由 Beat 触发：``task_id`` 是占位值，本任务会自动建一行增量任务再执行。
    """
    real_task_id = task_id or self.request.id

    # Beat 调用时（task_id=='scheduled-auto-incremental'）建增量任务行
    if real_task_id == "scheduled-auto-incremental":
        real_task_id = uuid.uuid4().hex

        async def _bootstrap_scheduled() -> None:
            async with pg_session() as s:
                await ImportTaskRepo(s).create(
                    task_id=real_task_id,
                    task_type=MarketImportTaskType.INCREMENTAL,
                    params={"source": "celery-beat"},
                )
                await s.commit()

        _run(_bootstrap_scheduled())

    async def _progress(event_type: str, data: dict) -> None:
        await publish(real_task_id, event_type, data)

    try:
        return _run(execute_import_task(task_id=real_task_id, progress_cb=_progress))
    except SoftTimeLimitExceeded:
        logger.error("market_import_soft_timeout", extra={"task_id": real_task_id})

        async def _fail() -> None:
            async with pg_session() as s:
                await ImportTaskRepo(s).mark_finished(
                    real_task_id,
                    status=MarketImportTaskStatus.FAILED,
                    error_message="任务超时",
                )
                await s.commit()
            await publish(real_task_id, "error", {"message": "任务超时"})

        _run(_fail())
        raise
    except Exception as exc:
        logger.exception("market_import_failed", extra={"task_id": real_task_id})

        async def _fail() -> None:
            async with pg_session() as s:
                await ImportTaskRepo(s).mark_finished(
                    real_task_id,
                    status=MarketImportTaskStatus.FAILED,
                    error_message=str(exc),
                )
                await s.commit()
            await publish(real_task_id, "error", {"message": str(exc)})

        _run(_fail())
        raise


# ─── 在线批量更新 ─────────────────────────────────────────────────────────────


@app.task(
    name="market.online_batch",
    bind=True,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=5,
    retry_backoff_max=120,
    retry_jitter=True,
    max_retries=2,
    soft_time_limit=7200,
    time_limit=7500,
)
def task_online_batch(self, task_id: str | None = None) -> dict:  # type: ignore[no-untyped-def]
    """按 (市场/代码 × 周期 × 日期范围) 在线批量更新历史 K 线。"""
    real_task_id = task_id or self.request.id

    async def _progress(event_type: str, data: dict) -> None:
        await publish(real_task_id, event_type, data)

    try:
        return _run(execute_batch_online_task(task_id=real_task_id, progress_cb=_progress))
    except SoftTimeLimitExceeded:
        logger.error("online_batch_soft_timeout", extra={"task_id": real_task_id})

        async def _fail() -> None:
            async with pg_session() as s:
                await ImportTaskRepo(s).mark_finished(
                    real_task_id,
                    status=MarketImportTaskStatus.FAILED,
                    error_message="任务超时",
                )
                await s.commit()
            await publish(real_task_id, "error", {"message": "任务超时"})

        _run(_fail())
        raise
    except Exception as exc:
        logger.exception("online_batch_failed", extra={"task_id": real_task_id})

        async def _fail() -> None:
            async with pg_session() as s:
                await ImportTaskRepo(s).mark_finished(
                    real_task_id,
                    status=MarketImportTaskStatus.FAILED,
                    error_message=str(exc),
                )
                await s.commit()
            await publish(real_task_id, "error", {"message": str(exc)})

        _run(_fail())
        raise


# ─── 主站测速 ────────────────────────────────────────────────────────────────


@app.task(name="market.test_hosts", soft_time_limit=60, time_limit=90)
def task_test_hosts() -> dict:
    hosts = _run(test_hosts())
    return {
        "total": len(hosts),
        "ok": sum(1 for h in hosts if h.status == "ok"),
        "best": hosts[0].to_dict() if hosts else None,
    }
