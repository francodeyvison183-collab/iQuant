"""在线批量更新历史行情用例。

批量路径完整对齐 ``HQScanner`` 的 TDX 反封禁策略：

- ``TdxConnectionPool.fetch_bars_in_range_resilient``：首页估算 count、页间退避、空响应 1.5s 原线重试、换线、全局冷却。
- ``iquant_market_data.tdx.batch_runner.run_tdx_batch``：自适应并发 2~8、连续 8 次失败熔断 60s、与池全局冷却联动。

单标的快捷入口仍走 ``fetch_and_save_online``（最近 N 根），不受上述分页策略约束。
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import date, datetime, time
from typing import Sequence

from iquant_domain.errors import TdxGlobalCooldown
from iquant_domain.market import KlinePeriod, Market
from iquant_market_data.tdx.batch_runner import (
    ADAPTIVE_MAX,
    ADAPTIVE_MIN,
    run_tdx_batch,
)

from ..config import get_market_settings
from ..db import pg_session, ts_session
from ..models import MarketImportTaskStatus, MarketImportTaskType
from ..repositories.import_task_repo import ImportTaskRepo
from ..repositories.market_bar_repo import MarketBarRepo
from ..repositories.symbol_repo import SymbolRepo
from .fetch_online import _ensure_source
from .schemas import ImportTaskRef

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, dict], Awaitable[None]]


def _parse_iso_date(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        if len(s) == 10:
            return datetime.combine(date.fromisoformat(s), time.min)
        return datetime.fromisoformat(s)
    except ValueError as exc:
        raise ValueError(f"非法日期字符串: {s!r}") from exc


async def enqueue_batch_online_task(
    *,
    markets: Sequence[Market] | None,
    periods: Sequence[KlinePeriod],
    codes: Sequence[str] | None,
    start_date: str,
    end_date: str | None,
    enqueuer: Callable[[str], None],
) -> ImportTaskRef:
    if not periods:
        raise ValueError("至少需要指定一个周期")
    if not (markets or codes):
        raise ValueError("至少需要指定 markets 或 codes 之一")
    start_dt = _parse_iso_date(start_date)
    if start_dt is None:
        raise ValueError("start_date 不能为空")
    end_dt = _parse_iso_date(end_date) if end_date else None
    if end_dt and end_dt < start_dt:
        raise ValueError("end_date 必须 >= start_date")

    task_id = uuid.uuid4().hex
    params = {
        "markets": [m.value for m in (markets or [])],
        "periods": [p.value for p in periods],
        "codes": list(codes or []),
        "start_date": start_dt.date().isoformat(),
        "end_date": (end_dt.date().isoformat() if end_dt else None),
    }
    async with pg_session() as s:
        await ImportTaskRepo(s).create(
            task_id=task_id,
            task_type=MarketImportTaskType.ONLINE_BATCH,
            params=params,
        )
        await s.commit()
    enqueuer(task_id)
    return ImportTaskRef(task_id=task_id, status=MarketImportTaskStatus.QUEUED.value)


async def _resolve_codes(
    *,
    markets: list[str],
    codes: list[str],
) -> list[str]:
    if codes:
        return [c.strip() for c in codes if c.strip()]
    if not markets:
        return []
    resolved: list[str] = []
    async with pg_session() as s:
        repo = SymbolRepo(s)
        for mkt in markets:
            rows, _total = await repo.list_paged(market=mkt, limit=10000, offset=0)
            resolved.extend(r.full_code for r in rows)
    return resolved


async def execute_batch_online_task(
    *,
    task_id: str,
    progress_cb: ProgressCallback | None = None,
    concurrency: int | None = None,
) -> dict:
    settings = get_market_settings()

    async with pg_session() as ses:
        task = await ImportTaskRepo(ses).get(task_id)
        if task is None:
            raise ValueError(f"任务不存在: {task_id}")
        params = task.params or {}
        await ImportTaskRepo(ses).mark_running(task_id)
        await ses.commit()

    start_dt = _parse_iso_date(params.get("start_date"))
    end_dt = _parse_iso_date(params.get("end_date"))
    if start_dt is None:
        raise ValueError("任务参数缺失 start_date")

    markets: list[str] = list(params.get("markets") or [])
    codes_raw: list[str] = list(params.get("codes") or [])
    periods = [KlinePeriod(p) for p in (params.get("periods") or [])]
    full_codes = await _resolve_codes(markets=markets, codes=codes_raw)

    pairs: list[tuple[str, KlinePeriod]] = [(fc, p) for fc in full_codes for p in periods]
    total = len(pairs)

    async with pg_session() as ses:
        await ImportTaskRepo(ses).update_progress(task_id, total_files=total)
        await ses.commit()
    if progress_cb:
        await progress_cb(
            "progress",
            {
                "task_id": task_id,
                "total_files": total,
                "done_files": 0,
                "imported_bars": 0,
                "error_count": 0,
                "markets": markets,
                "periods": [p.value for p in periods],
                "code_count": len(full_codes),
            },
        )

    if total == 0:
        async with pg_session() as ses:
            await ImportTaskRepo(ses).mark_finished(
                task_id,
                status=MarketImportTaskStatus.SUCCEEDED,
                error_message="没有可处理的标的或周期",
            )
            await ses.commit()
        result = {"task_id": task_id, "total_files": 0, "done_files": 0, "imported_bars": 0}
        if progress_cb:
            await progress_cb("done", result)
        return result

    source = _ensure_source()
    pool = source.pool
    user_cap = concurrency or settings.tdx_pool_size
    maximum = min(ADAPTIVE_MAX, pool.max_size, max(ADAPTIVE_MIN, user_cap))
    initial = min(4, maximum)

    state = {"done": 0, "bars": 0, "errors": 0}
    prog_lock = asyncio.Lock()
    report_every = 20
    last_reported = 0

    async def flush_progress(*, force: bool = False) -> None:
        nonlocal last_reported
        async with prog_lock:
            done = int(state["done"])
            bars = int(state["bars"])
            errors = int(state["errors"])
        if not force and done - last_reported < report_every and done < total:
            return
        last_reported = done
        async with pg_session() as ses:
            await ImportTaskRepo(ses).update_progress(
                task_id,
                done_files=done,
                imported_bars=bars,
                error_count=errors,
            )
            await ses.commit()
        if progress_cb:
            await progress_cb(
                "progress",
                {
                    "task_id": task_id,
                    "total_files": total,
                    "done_files": done,
                    "imported_bars": bars,
                    "error_count": errors,
                },
            )

    async def process_one(pair: tuple[str, KlinePeriod]) -> bool:
        fc, period = pair
        try:
            batch = await pool.fetch_bars_in_range_resilient(
                full_code=fc,
                period=period,
                start=start_dt,
                end=end_dt,
            )
        except TdxGlobalCooldown:
            async with prog_lock:
                state["done"] += 1
                state["errors"] += 1
            await flush_progress()
            return False
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "online_batch_fetch_failed",
                extra={"full_code": fc, "period": period.value, "error": str(exc)},
            )
            async with prog_lock:
                state["done"] += 1
                state["errors"] += 1
            await flush_progress()
            return False

        if batch.is_empty:
            async with prog_lock:
                state["done"] += 1
                state["errors"] += 1
            await flush_progress()
            return False

        try:
            async with ts_session() as ts:
                inserted = await MarketBarRepo(ts).bulk_upsert(
                    batch.bars, source="tdx-online"
                )
                await ts.commit()
        except Exception:
            logger.exception(
                "online_batch_upsert_failed",
                extra={"full_code": fc, "period": period.value},
            )
            async with prog_lock:
                state["done"] += 1
                state["errors"] += 1
            await flush_progress()
            return False

        async with prog_lock:
            state["done"] += 1
            state["bars"] += inserted
        await flush_progress()
        return True

    _stats = await run_tdx_batch(
        pairs,
        process_one,
        name=f"online_batch:{task_id[:8]}",
        initial=initial,
        minimum=ADAPTIVE_MIN,
        maximum=maximum,
        get_pool_cooldown_until=lambda: pool.global_cooldown_until,
    )
    await flush_progress(force=True)

    async with pg_session() as ses:
        await ImportTaskRepo(ses).mark_finished(
            task_id, status=MarketImportTaskStatus.SUCCEEDED
        )
        await ses.commit()

    result = {
        "task_id": task_id,
        "total_files": total,
        "done_files": int(state["done"]),
        "imported_bars": int(state["bars"]),
        "error_count": int(state["errors"]),
        "runner": _stats,
    }
    if progress_cb:
        await progress_cb("done", result)
    return result
