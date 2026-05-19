"""回测任务 REST（迭代 V0.2b）。"""
from __future__ import annotations

import os
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query

from iquant_backtest_service.usecases import backtests as bt_uc
from iquant_backtest_service.usecases.schemas import BacktestCreateIn
from iquant_domain.errors import ValidationError
from iquant_identity_service.usecases.schemas import AdminProfile

from ...deps import require_admin

router = APIRouter(
    prefix="/backtests",
    tags=["backtests"],
    dependencies=[Depends(require_admin)],
)


def _idem(x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key")) -> str:
    if not x_idempotency_key or len(x_idempotency_key.strip()) < 8:
        raise ValidationError("请求头 X-Idempotency-Key 必填且至少 8 字符")
    return x_idempotency_key.strip()[:128]


async def _dispatch_backtest(task_id: UUID) -> None:
    """优先 Celery；不可用时在 API 进程内执行（开发兜底）。"""
    try:
        from celery import Celery

        broker = os.environ.get("IQUANT_CELERY_BROKER_URL", "redis://redis:6379/1")
        celery_app = Celery(broker=broker)
        celery_app.send_task(
            "strategy.run_backtest",
            args=[str(task_id)],
            queue="default",
        )
    except Exception:
        await bt_uc.execute_backtest_task(task_id=task_id)


@router.post("")
async def api_create_backtest(
    body: BacktestCreateIn,
    background_tasks: BackgroundTasks,
    admin: AdminProfile = Depends(require_admin),
    idempotency_key: str = Depends(_idem),
) -> dict:
    out = await bt_uc.create_backtest_task(
        admin_user_id=admin.id,
        body=body,
        idempotency_key=idempotency_key,
    )
    background_tasks.add_task(_dispatch_backtest, out.id)
    return {"code": 0, "data": out.model_dump(mode="json")}


@router.get("")
async def api_list_backtests(
    admin: AdminProfile = Depends(require_admin),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    rows, total = await bt_uc.list_backtest_tasks(
        admin_user_id=admin.id, limit=limit, offset=offset
    )
    return {
        "code": 0,
        "data": [r.model_dump(mode="json") for r in rows],
        "total": total,
    }


@router.get("/{task_id}")
async def api_get_backtest(
    task_id: UUID,
    admin: AdminProfile = Depends(require_admin),
) -> dict:
    out = await bt_uc.get_backtest_task(admin_user_id=admin.id, task_id=task_id)
    return {"code": 0, "data": out.model_dump(mode="json")}
