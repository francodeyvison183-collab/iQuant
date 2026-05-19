"""在线批量更新历史行情用例。

批量在线更新的 TDX 反封禁策略：

- ``TdxConnectionPool.fetch_bars_in_range_resilient``：首页估算 count、页间退避、空响应 1.5s 原线重试、换线、全局冷却。
- ``iquant_market_data.tdx.batch_runner.run_tdx_batch``：自适应并发 2~8、连续 8 次失败熔断 60s、与池全局冷却联动。

单只标的可在任务参数中填写 ``codes``，仍走上述分页拉取策略。
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import time as time_mod
import uuid
from collections.abc import Awaitable, Callable
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from iquant_market_data.tdx.pool import TdxConnectionPool

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
from .schemas import ImportTaskRef

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, dict], Awaitable[None]]


def build_runtime_progress_fields(
    *,
    started_at: float,
    done: int,
    total: int,
    runtime_stats: dict | None,
    concurrency_max: int,
    concurrency_initial: int,
) -> dict[str, int | float | None]:
    """在线批量任务 SSE 附带的耗时 / ETA / 并发快照。"""
    elapsed = max(0.0, time_mod.monotonic() - started_at)
    remaining = max(0, total - done)
    eta: float | None = None
    speed_per_minute = 0.0
    if done > 0 and elapsed > 0:
        rate = done / elapsed
        speed_per_minute = rate * 60.0
        if remaining > 0:
            eta = remaining / rate

    gate = (runtime_stats or {}).get("gate") or {}
    cap = int(gate.get("cap") or 0)
    active = int(gate.get("active") or 0)

    out: dict[str, int | float | None] = {
        "elapsed_seconds": round(elapsed, 1),
        "eta_seconds": round(eta, 1) if eta is not None else None,
        "speed_per_minute": round(speed_per_minute, 1),
        "concurrency_cap": cap if cap > 0 else concurrency_initial,
        "concurrency_active": active,
        "concurrency_max": concurrency_max,
    }
    pool_remain = float((runtime_stats or {}).get("pool_cooldown_remain_seconds") or 0)
    if pool_remain > 0:
        out["pool_cooldown_remain_seconds"] = round(pool_remain, 1)
    batch_until = float((runtime_stats or {}).get("batch_cooldown_until") or 0)
    batch_remain = max(0.0, batch_until - time_mod.time())
    if batch_remain > 0:
        out["batch_cooldown_remain_seconds"] = round(batch_remain, 1)
    return out


def _parse_iso_date(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        if len(s) == 10:
            return datetime.combine(date.fromisoformat(s), time.min)
        return datetime.fromisoformat(s)
    except ValueError as exc:
        raise ValueError(f"非法日期字符串: {s!r}") from exc


def _parse_range_end(s: str | None) -> datetime | None:
    """日期字符串的结束边界：含当日全天（日线 bar_time 多为 15:00，不能用 00:00）。"""
    if not s:
        return None
    if len(s) == 10:
        d = date.fromisoformat(s)
        return datetime.combine(d, time(23, 59, 59, 999999))
    dt = datetime.fromisoformat(s)
    if dt.hour == 0 and dt.minute == 0 and dt.second == 0 and dt.microsecond == 0:
        return dt + timedelta(days=1) - timedelta(microseconds=1)
    return dt


async def enqueue_batch_online_task(
    *,
    markets: Sequence[str] | None,
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
    end_dt = _parse_range_end(end_date) if end_date else None
    if end_dt and end_dt < start_dt:
        raise ValueError("end_date 必须 >= start_date")

    task_id = uuid.uuid4().hex
    params = {
        "markets": list(markets or []),
        "periods": [p.value for p in periods],
        "codes": list(codes or []),
        "start_date": start_dt.date().isoformat(),
        "end_date": (end_date if end_date else None),
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
    pool: TdxConnectionPool,
    pairs: list[tuple[str, str]] | None = None,
) -> list[str]:
    """解析批量标的：显式 codes 优先；否则经 pytdx 拉全 A 股代码表。

    支持虚拟市场 ``cyb`` / ``kcb``，在 TDX 列表结果上按前缀过滤。
    ``pairs`` 可由上游同步名称时一并拉取，避免重复请求 TDX。
    """
    from iquant_market_data.tdx.codes import is_in_virtual_markets

    if codes:
        resolved = [c.strip().lower() for c in codes if c.strip()]
        if markets:
            resolved = [fc for fc in resolved if is_in_virtual_markets(fc, markets)]
        return resolved

    if pairs is None:
        from .sync_symbols import fetch_a_share_pairs

        pairs = await fetch_a_share_pairs(pool=pool)

    all_fc = [fc for fc, _ in pairs]
    if not all_fc:
        logger.error(
            "tdx_a_share_list_empty",
            extra={"markets": markets, "hint": "主站不可用或证券列表协议解析失败"},
        )
        return []
    if not markets:
        return all_fc
    filtered = [fc for fc in all_fc if is_in_virtual_markets(fc, markets)]
    if not filtered and all_fc:
        logger.warning(
            "tdx_a_share_market_filter_empty",
            extra={"markets": markets, "total_before_filter": len(all_fc)},
        )
    return filtered


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
    end_dt = _parse_range_end(params.get("end_date"))
    if start_dt is None:
        raise ValueError("任务参数缺失 start_date")

    markets: list[str] = list(params.get("markets") or [])
    codes_raw: list[str] = list(params.get("codes") or [])
    periods = [KlinePeriod(p) for p in (params.get("periods") or [])]

    from .fetch_online import reload_tdx_source

    source = reload_tdx_source()
    pool = source.pool
    pool.reload_hosts()

    from .sync_symbols import fetch_a_share_pairs, sync_symbols_from_pairs

    a_share_pairs = await fetch_a_share_pairs(pool=pool)
    symbol_sync = await sync_symbols_from_pairs(a_share_pairs)
    logger.info("batch_online_symbol_sync", extra=symbol_sync)

    full_codes = await _resolve_codes(
        markets=markets,
        codes=codes_raw,
        pool=pool,
        pairs=a_share_pairs,
    )

    pairs: list[tuple[str, KlinePeriod]] = [(fc, p) for fc in full_codes for p in periods]
    total = len(pairs)

    async with pg_session() as ses:
        task_row = await ImportTaskRepo(ses).get(task_id)
        if task_row is not None:
            task_row.params = {
                **(task_row.params or {}),
                "code_count": len(full_codes),
            }
        await ImportTaskRepo(ses).update_progress(task_id, total_files=total)
        await ses.commit()

    if total == 0:
        msg = (
            "没有可处理的标的：请先在「TDX 主站」页测速并确保有可用主站；"
            "或填写具体代码（如 sh600519）。若已选市场但列表为空，多为 TDX 连接/列表拉取失败，请查看 worker 日志 tdx_a_share_list_empty"
        )
        async with pg_session() as ses:
            await ImportTaskRepo(ses).mark_finished(
                task_id,
                status=MarketImportTaskStatus.FAILED,
                error_message=msg,
            )
            await ses.commit()
        result = {"task_id": task_id, "total_files": 0, "done_files": 0, "imported_bars": 0}
        if progress_cb:
            await progress_cb("error", {"message": msg, **result})
        return result

    user_cap = concurrency or settings.tdx_pool_size
    maximum = min(ADAPTIVE_MAX, pool.max_size, max(ADAPTIVE_MIN, user_cap))
    initial = min(4, maximum)

    if progress_cb:
        await progress_cb(
            "progress",
            {
                "task_id": task_id,
                "task_type": MarketImportTaskType.ONLINE_BATCH.value,
                "total_files": total,
                "done_files": 0,
                "imported_bars": 0,
                "error_count": 0,
                "markets": markets,
                "periods": [p.value for p in periods],
                "code_count": len(full_codes),
                "concurrency_cap": initial,
                "concurrency_active": 0,
                "concurrency_max": maximum,
                "elapsed_seconds": 0.0,
                "eta_seconds": None,
                "speed_per_minute": 0.0,
            },
        )

    state = {"done": 0, "bars": 0, "errors": 0}
    recent_imported = []
    prog_lock = asyncio.Lock()
    report_every = 20
    last_reported = 0
    started_at = time_mod.monotonic()
    runtime_stats: dict = {}

    def _runtime_fields() -> dict[str, int | float | None]:
        return build_runtime_progress_fields(
            started_at=started_at,
            done=int(state["done"]),
            total=total,
            runtime_stats=runtime_stats,
            concurrency_max=maximum,
            concurrency_initial=initial,
        )

    async def flush_progress(*, force: bool = False, heartbeat: bool = False) -> None:
        nonlocal last_reported, recent_imported
        async with prog_lock:
            done = int(state["done"])
            bars = int(state["bars"])
            errors = int(state["errors"])
            current_recent = list(recent_imported)
            if (
                not force
                and not heartbeat
                and done - last_reported < report_every
                and done < total
            ):
                return
            if heartbeat and not current_recent:
                recent_imported = []
            else:
                recent_imported = []
        
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
                    "task_type": MarketImportTaskType.ONLINE_BATCH.value,
                    "total_files": total,
                    "done_files": done,
                    "imported_bars": bars,
                    "error_count": errors,
                    "recent_imported": current_recent,
                    **_runtime_fields(),
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
            recent_imported.append({
                "full_code": fc,
                "period": period.value,
                "inserted": inserted
            })
        await flush_progress()
        return True

    async def _heartbeat() -> None:
        while int(state["done"]) < total:
            await asyncio.sleep(2)
            await flush_progress(heartbeat=True)

    heartbeat_task = asyncio.create_task(_heartbeat())
    try:
        _stats = await run_tdx_batch(
            pairs,
            process_one,
            name=f"online_batch:{task_id[:8]}",
            initial=initial,
            minimum=ADAPTIVE_MIN,
            maximum=maximum,
            get_pool_cooldown_until=lambda: pool.global_cooldown_until,
            runtime_stats=runtime_stats,
        )
    finally:
        heartbeat_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await heartbeat_task
    await flush_progress(force=True)

    imported = int(state["bars"])
    errors = int(state["errors"])
    if imported == 0 and errors >= total:
        finish_status = MarketImportTaskStatus.FAILED
        finish_msg = (
            "全部组合均未拉到数据：请检查 TDX 主站是否已测速可用，"
            "或缩小日期范围后重试"
        )
    elif imported == 0:
        finish_status = MarketImportTaskStatus.FAILED
        finish_msg = "未写入任何 K 线（TDX 返回为空或均已存在）"
    else:
        finish_status = MarketImportTaskStatus.SUCCEEDED
        finish_msg = None

    async with pg_session() as ses:
        await ImportTaskRepo(ses).mark_finished(
            task_id, status=finish_status, error_message=finish_msg
        )
        await ses.commit()

    result = {
        "task_id": task_id,
        "task_type": MarketImportTaskType.ONLINE_BATCH.value,
        "total_files": total,
        "done_files": int(state["done"]),
        "imported_bars": int(state["bars"]),
        "error_count": int(state["errors"]),
        "runner": _stats,
        **_runtime_fields(),
    }
    if progress_cb:
        event = "done" if finish_status == MarketImportTaskStatus.SUCCEEDED else "error"
        payload = {**result, "message": finish_msg} if finish_msg else result
        await progress_cb(event, payload)
    return result
