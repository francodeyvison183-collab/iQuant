"""本地 TDX 文件导入用例。

入口分为两部分：

* :func:`enqueue_import_task` —— API 调用，事务内建任务行 + 投递 Celery 任务，立即返回。
* :func:`execute_import_task` —— Celery worker 调用，逐文件解析并写入 TimescaleDB。
"""
from __future__ import annotations

import logging
import uuid
from typing import Awaitable, Callable

from iquant_domain.market import KlinePeriod
from iquant_market_data.tdx.codes import split_full_code
from iquant_market_data.tdx.file_parser import (
    get_record_count,
    parse_day_file,
    parse_lc5_file,
)
from iquant_market_data.tdx.file_scanner import scan_changed_files

from ..config import get_market_settings
from ..db import pg_session, ts_session
from ..models import MarketImportTaskStatus, MarketImportTaskType
from ..repositories.import_task_repo import ImportStateRepo, ImportTaskRepo
from ..repositories.market_bar_repo import MarketBarRepo
from ..repositories.symbol_repo import SymbolRepo
from .schemas import ImportTaskRef

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, dict], Awaitable[None]]


async def enqueue_import_task(
    *,
    task_type: MarketImportTaskType,
    vipdoc_dir: str | None = None,
    enqueuer: Callable[[str], None],
) -> ImportTaskRef:
    """创建导入任务并投递到 Celery。enqueuer 由 API 层注入，避免服务层依赖 Celery 实例。"""
    task_id = uuid.uuid4().hex
    params = {"vipdoc_dir": vipdoc_dir or get_market_settings().tdx_vipdoc_dir}
    async with pg_session() as s:
        await ImportTaskRepo(s).create(
            task_id=task_id, task_type=task_type, params=params
        )
        await s.commit()
    enqueuer(task_id)  # commit 之后再发任务，保证不丢
    return ImportTaskRef(task_id=task_id, status=MarketImportTaskStatus.QUEUED.value)


async def execute_import_task(
    *,
    task_id: str,
    progress_cb: ProgressCallback | None = None,
) -> dict:
    """worker 侧执行：扫描 vipdoc → 解析 → 写 TimescaleDB → 更新状态。"""
    s = get_market_settings()

    async with pg_session() as ses:
        task = await ImportTaskRepo(ses).get(task_id)
        if task is None:
            raise ValueError(f"任务不存在: {task_id}")
        task_type = MarketImportTaskType(task.task_type)
        vipdoc_dir = (task.params or {}).get("vipdoc_dir") or s.tdx_vipdoc_dir
        await ImportTaskRepo(ses).mark_running(task_id)
        await ses.commit()

    if progress_cb:
        await progress_cb("start", {"task_id": task_id, "vipdoc_dir": vipdoc_dir})

    # 1) 扫描并对比状态
    async with pg_session() as ses:
        state_map = await ImportStateRepo(ses).load_state_map()

    if task_type == MarketImportTaskType.FULL:
        from iquant_market_data.tdx.file_scanner import scan_tdx_files

        files = scan_tdx_files(vipdoc_dir)
    else:
        changed, _unchanged = scan_changed_files(
            vipdoc_dir,
            state_map={k: (v[0], v[1]) for k, v in state_map.items()},
        )
        files = changed

    total_files = len(files)
    async with pg_session() as ses:
        await ImportTaskRepo(ses).update_progress(task_id, total_files=total_files)
        await ses.commit()

    if progress_cb:
        await progress_cb("progress", {"task_id": task_id, "total_files": total_files, "done_files": 0})

    # 2) 逐文件导入
    imported_bars = 0
    error_count = 0
    done_files = 0

    for fi in files:
        try:
            prev = state_map.get(fi.file_path)
            offset = prev[2] if (task_type != MarketImportTaskType.FULL and prev) else 0

            if fi.period == KlinePeriod.DAY:
                bars = list(parse_day_file(fi.file_path, full_code=fi.full_code, record_offset=offset))
            elif fi.period == KlinePeriod.MIN_5:
                bars = list(parse_lc5_file(fi.file_path, full_code=fi.full_code, record_offset=offset))
            else:
                bars = []

            if bars:
                async with ts_session() as ts:
                    inserted = await MarketBarRepo(ts).bulk_upsert(bars, source="tdx-file")
                    await ts.commit()
                imported_bars += inserted

            last_bar_time = bars[-1].bar_time if bars else None

            async with pg_session() as ses:
                market, code = split_full_code(fi.full_code)
                await SymbolRepo(ses).upsert_basic(fi.full_code, market, code)
                await ImportStateRepo(ses).upsert(
                    file_path=fi.file_path,
                    full_code=fi.full_code,
                    period=fi.period.value,
                    file_size=fi.file_size,
                    file_mtime=fi.file_mtime,
                    imported_records=get_record_count(fi.file_path),
                    last_bar_time=last_bar_time,
                    last_task_id=task_id,
                )
                await ses.commit()
        except Exception as exc:  # noqa: BLE001 - 单文件失败不阻塞整个任务
            error_count += 1
            logger.exception("tdx_import_file_failed", extra={"file": fi.file_path, "error": str(exc)})

        done_files += 1
        if done_files % 50 == 0 or done_files == total_files:
            async with pg_session() as ses:
                await ImportTaskRepo(ses).update_progress(
                    task_id,
                    done_files=done_files,
                    imported_bars=imported_bars,
                    error_count=error_count,
                )
                await ses.commit()
            if progress_cb:
                await progress_cb(
                    "progress",
                    {
                        "task_id": task_id,
                        "total_files": total_files,
                        "done_files": done_files,
                        "imported_bars": imported_bars,
                        "error_count": error_count,
                    },
                )

    # 3) 收尾
    async with pg_session() as ses:
        await ImportTaskRepo(ses).update_progress(
            task_id,
            done_files=done_files,
            imported_bars=imported_bars,
            error_count=error_count,
        )
        await ImportTaskRepo(ses).mark_finished(
            task_id, status=MarketImportTaskStatus.SUCCEEDED
        )
        await ses.commit()

    result = {
        "task_id": task_id,
        "total_files": total_files,
        "done_files": done_files,
        "imported_bars": imported_bars,
        "error_count": error_count,
    }
    if progress_cb:
        await progress_cb("done", result)
    return result
