"""行情后台管理 REST 路由。

为了让前端 admin-web 开箱即用，路由统一挂在 ``/api/v1/admin/market/*``，
所有响应使用 ``{"code": 0, "data": ..., "message": ...}`` 风格，
与 admin-web（pure-admin 模板）的前端约定保持一致。
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import AsyncIterator

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from iquant_domain.market import KlinePeriod, Market
from iquant_market_service.db import pg_session
from iquant_market_service.models import MarketImportTaskType
from iquant_market_service.progress_bus import subscribe
from iquant_market_service.repositories.import_task_repo import ImportTaskRepo
from iquant_market_service.repositories.symbol_repo import SymbolRepo
from iquant_market_service.usecases.batch_online_fetch import enqueue_batch_online_task
from iquant_market_service.usecases.fetch_online import fetch_and_save_online
from iquant_market_service.usecases.import_local import enqueue_import_task
from iquant_market_service.usecases.manage_hosts import (
    add_host,
    import_hosts_from_cfg,
    list_hosts,
    remove_host,
    test_hosts,
)
from iquant_market_service.usecases.query_bars import get_symbol_coverage, query_bars
from iquant_market_service.usecases.scan_local import scan_local_preview

from ...bootstrap import enqueue_market_import, enqueue_online_batch

# 通达信 connect.cfg 通常 < 16 KiB，给个宽松的安全上限避免上传超大文件
_MAX_CFG_BYTES = 256 * 1024

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/market", tags=["admin-market"])


# ─── 主站管理 ──────────────────────────────────────────────────────────────────


class TdxHostIn(BaseModel):
    ip: str = Field(min_length=7, max_length=64)
    port: int = Field(ge=1, le=65535)
    name: str = Field(default="", max_length=64)


@router.get("/hosts")
async def api_list_hosts() -> dict:
    hosts = await list_hosts()
    return {"code": 0, "data": hosts}


@router.post("/hosts")
async def api_add_host(payload: TdxHostIn) -> dict:
    try:
        host = await add_host(ip=payload.ip, port=payload.port, name=payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"code": 0, "data": host.to_dict()}


@router.delete("/hosts/{host_id}")
async def api_remove_host(host_id: int) -> dict:
    ok = await remove_host(host_id=host_id)
    if not ok:
        raise HTTPException(status_code=404, detail="主站不存在或为内置主站")
    return {"code": 0, "message": "已删除"}


@router.post("/hosts/test")
async def api_test_hosts() -> dict:
    hosts = await test_hosts()
    return {"code": 0, "data": [h.to_dict() for h in hosts]}


@router.post("/hosts/import-cfg")
async def api_import_hosts_cfg(
    file: UploadFile = File(...),
    only_quote_ports: bool = Query(default=True),
    run_test: bool = Query(default=True),
) -> dict:
    """上传通达信 ``connect.cfg`` 文件批量导入主站。

    - ``only_quote_ports``：仅保留 7709/7708 行情口（默认 True；扩展 7727 不返回 K 线）。
    - ``run_test``：导入后立即触发一次全量测速（默认 True）。
    """
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="文件为空")
    if len(raw) > _MAX_CFG_BYTES:
        raise HTTPException(
            status_code=413, detail=f"文件过大，最大 {_MAX_CFG_BYTES // 1024} KiB"
        )
    try:
        result = await import_hosts_from_cfg(
            raw, only_quote_ports=only_quote_ports, run_test=run_test
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"code": 0, "data": result}


# ─── 本地 vipdoc 扫描 ──────────────────────────────────────────────────────────


class ScanPreviewIn(BaseModel):
    vipdoc_dir: str | None = None
    markets: list[str] | None = None


@router.post("/scan/preview")
async def api_scan_preview(payload: ScanPreviewIn) -> dict:
    result = await scan_local_preview(vipdoc_dir=payload.vipdoc_dir, markets=payload.markets)
    return {"code": 0, "data": result.model_dump()}


@router.post("/upload-vipdoc")
async def api_upload_vipdoc(
    upload_id: str = Form(...),
    file_paths: str = Form(...),
    files: list[UploadFile] = File(...),
) -> dict:
    paths = json.loads(file_paths)
    if len(paths) != len(files):
        raise HTTPException(status_code=400, detail="paths and files length mismatch")
    
    base_dir = Path("storage/local/uploads") / f"vipdoc_{upload_id}"
    base_dir.mkdir(parents=True, exist_ok=True)
    
    for path, file_obj in zip(paths, files):
        dest = base_dir / path.lstrip("/")
        dest.parent.mkdir(parents=True, exist_ok=True)
        content = await file_obj.read()
        dest.write_bytes(content)
        
    return {"code": 0, "data": {"vipdoc_dir": str(base_dir.absolute())}}


# ─── 导入任务 ──────────────────────────────────────────────────────────────────


class CreateImportTaskIn(BaseModel):
    task_type: MarketImportTaskType = MarketImportTaskType.INCREMENTAL
    vipdoc_dir: str | None = None
    markets: list[str] | None = None


@router.post("/import-tasks")
async def api_create_import_task(payload: CreateImportTaskIn) -> dict:
    ref = await enqueue_import_task(
        task_type=payload.task_type,
        vipdoc_dir=payload.vipdoc_dir,
        markets=payload.markets,
        enqueuer=enqueue_market_import,
    )
    return {"code": 0, "data": ref.model_dump()}


def _task_to_dict(row) -> dict:  # type: ignore[no-untyped-def]
    params = row.params or {}
    return {
        "task_id": row.task_id,
        "task_type": row.task_type,
        "status": row.status,
        "params": params,
        "code_count": params.get("code_count")
        or (row.total_files // len(params["periods"]) if params.get("periods") and row.total_files else 0),
        "markets": params.get("markets"),
        "periods": params.get("periods"),
        "total_files": row.total_files,
        "done_files": row.done_files,
        "imported_bars": row.imported_bars,
        "error_count": row.error_count,
        "error_message": row.error_message,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/import-tasks")
async def api_list_import_tasks(
    status: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    async with pg_session() as s:
        rows, total = await ImportTaskRepo(s).list_paged(status=status, limit=limit, offset=offset)
    return {"code": 0, "data": [_task_to_dict(r) for r in rows], "total": total}


@router.get("/import-tasks/{task_id}")
async def api_get_import_task(task_id: str) -> dict:
    async with pg_session() as s:
        row = await ImportTaskRepo(s).get(task_id)
    if row is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"code": 0, "data": _task_to_dict(row)}


@router.post("/import-tasks/{task_id}/retry")
async def api_retry_import_task(task_id: str) -> dict:
    async with pg_session() as s:
        repo = ImportTaskRepo(s)
        task = await repo.reset(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="任务不存在")

        await s.commit()

        if task.task_type in (MarketImportTaskType.INCREMENTAL, MarketImportTaskType.FULL):
            enqueue_market_import(task_id)
        elif task.task_type == MarketImportTaskType.ONLINE_BATCH:
            enqueue_online_batch(task_id)

    return {"code": 0, "message": "任务已重新入队"}


@router.get("/import-tasks/{task_id}/progress")
async def api_task_progress(task_id: str) -> EventSourceResponse:
    """SSE 实时进度。"""

    async def event_stream() -> AsyncIterator[dict]:
        async with pg_session() as s:
            row = await ImportTaskRepo(s).get(task_id)
        if row is None:
            yield {"event": "error", "data": json.dumps({"message": "任务不存在"})}
            return
        # 历史快照先打一发，避免前端等不到首个事件
        yield {"event": "progress", "data": json.dumps(_task_to_dict(row))}
        if row.status in ("succeeded", "failed", "cancelled"):
            yield {"event": "done", "data": json.dumps(_task_to_dict(row))}
            return

        async with subscribe(task_id) as messages:
            try:
                async for msg in messages:
                    yield {"event": msg.get("type", "progress"), "data": json.dumps(msg.get("data", {}))}
                    if msg.get("type") in ("done", "error", "cancelled"):
                        return
            except asyncio.CancelledError:
                return

    return EventSourceResponse(event_stream())


# ─── 在线行情拉取 ─────────────────────────────────────────────────────────────


class OnlineFetchIn(BaseModel):
    full_code: str
    period: KlinePeriod = KlinePeriod.DAY
    max_count: int = Field(default=800, ge=1, le=8000)


@router.post("/online/fetch")
async def api_online_fetch(payload: OnlineFetchIn) -> dict:
    inserted = await fetch_and_save_online(
        full_code=payload.full_code,
        period=payload.period,
        max_count=payload.max_count,
    )
    return {"code": 0, "data": {"inserted": inserted}}


class OnlineBatchIn(BaseModel):
    """在线批量更新入参。

    - ``markets``：市场列表；``codes`` 为空时经 pytdx 拉全 A 股列表再按市场筛选。
    - ``codes``：显式标的列表（``sh600519`` 形式），优先级高于 ``markets``。
    - ``periods``：周期列表，至少 1 个；MVP 支持 5m/30m/day/week 等。
    - ``start_date``：必填，``YYYY-MM-DD`` 或 ISO 时间字符串。
    - ``end_date``：可选；省略表示到今天。
    """

    markets: list[str] | None = None
    codes: list[str] | None = None
    periods: list[KlinePeriod] = Field(default_factory=list)
    start_date: str
    end_date: str | None = None


@router.post("/online/batch")
async def api_online_batch(payload: OnlineBatchIn) -> dict:
    try:
        ref = await enqueue_batch_online_task(
            markets=payload.markets,
            periods=payload.periods,
            codes=payload.codes,
            start_date=payload.start_date,
            end_date=payload.end_date,
            enqueuer=enqueue_online_batch,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"code": 0, "data": ref.model_dump()}


# ─── 数据查看 ─────────────────────────────────────────────────────────────────


@router.get("/symbols")
async def api_list_symbols(
    market: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    async with pg_session() as s:
        rows, total = await SymbolRepo(s).list_paged(
            market=market, keyword=keyword, limit=limit, offset=offset
        )
    return {
        "code": 0,
        "data": [
            {
                "full_code": r.full_code,
                "code": r.code,
                "market": r.market,
                "name": r.name,
                "asset_type": r.asset_type,
                "list_date": r.list_date.isoformat() if r.list_date else None,
            }
            for r in rows
        ],
        "total": total,
    }


@router.get("/bars")
async def api_query_bars(
    full_code: str = Query(...),
    period: KlinePeriod = Query(default=KlinePeriod.DAY),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=5000),
) -> dict:
    result = await query_bars(
        full_code=full_code, period=period, start=start, end=end, limit=limit
    )
    return {"code": 0, "data": result.model_dump()}


@router.get("/coverage")
async def api_symbol_coverage(
    full_code: str = Query(...),
    period: KlinePeriod = Query(default=KlinePeriod.DAY),
) -> dict:
    cov = await get_symbol_coverage(full_code=full_code, period=period)
    return {"code": 0, "data": cov.model_dump()}
