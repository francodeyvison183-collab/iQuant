"""策略与回测 Celery 任务。"""
from __future__ import annotations

import logging
import uuid

from celery.exceptions import SoftTimeLimitExceeded

from iquant_backtest_service.usecases.backtests import execute_backtest_task
from iquant_domain.errors import IquantError

from ..celery_app import app

logger = logging.getLogger(__name__)


def _run(coro):  # type: ignore[no-untyped-def]
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@app.task(
    name="strategy.run_backtest",
    bind=True,
    max_retries=2,
    soft_time_limit=120,
    time_limit=180,
)
def run_backtest(self, task_id: str) -> dict[str, str]:  # type: ignore[no-untyped-def]
    """执行回测任务（委托 backtest-service 用例）。"""
    try:
        _run(execute_backtest_task(task_id=uuid.UUID(task_id)))
        return {"status": "succeeded", "task_id": task_id}
    except SoftTimeLimitExceeded:
        logger.exception("backtest_soft_time_limit", extra={"task_id": task_id})
        raise
    except IquantError:
        logger.exception("backtest_task_business_error", extra={"task_id": task_id})
        raise
    except Exception as exc:
        logger.exception("backtest_task_error", extra={"task_id": task_id})
        raise self.retry(exc=exc, countdown=30) from exc
