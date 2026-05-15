"""TDX 批次任务调度：自适应并发与熔断。

核心：自适应并发、批次级熔断、与连接池全局冷却联动。常量来自 TDX 批量拉取压测，
修改前请阅读 ``docs/architecture/modules/market-data.md`` 反封禁章节。
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, Sequence, TypeVar

from .ban_diagnostic import log_ban_diagnostic

logger = logging.getLogger(__name__)

ADAPTIVE_INITIAL = 4
ADAPTIVE_MIN = 2
ADAPTIVE_MAX = 8
ADAPTIVE_GROW_SUCC = 200
ADAPTIVE_SHRINK_DELTA = 2

BATCH_FAIL_BURST_THRESHOLD = 8
BATCH_COOLDOWN_SECONDS = 60

T = TypeVar("T")


class AdaptiveConcurrency:
    """自适应并发门（每个批次一份实例）。"""

    def __init__(
        self,
        *,
        initial: int = ADAPTIVE_INITIAL,
        minimum: int = ADAPTIVE_MIN,
        maximum: int = ADAPTIVE_MAX,
    ) -> None:
        self.cap = max(minimum, min(initial, maximum))
        self.minimum = minimum
        self.maximum = maximum
        self.active = 0
        self.success_streak = 0
        self.total_success = 0
        self.total_fail = 0
        self.grow_events = 0
        self.shrink_events = 0
        self._cond = asyncio.Condition()

    async def acquire(self) -> None:
        async with self._cond:
            while self.active >= self.cap:
                await self._cond.wait()
            self.active += 1

    async def release(self) -> None:
        async with self._cond:
            self.active -= 1
            self._cond.notify_all()

    async def on_success(self, batch_id: str = "") -> None:
        async with self._cond:
            self.total_success += 1
            self.success_streak += 1
            if self.success_streak >= ADAPTIVE_GROW_SUCC and self.cap < self.maximum:
                self.cap += 1
                self.success_streak = 0
                self.grow_events += 1
                self._cond.notify_all()
                logger.info(
                    "[AdaptiveConcurrency] batch=%s 连续 %s 成功 → cap %s→%s",
                    batch_id,
                    ADAPTIVE_GROW_SUCC,
                    self.cap - 1,
                    self.cap,
                )

    async def on_failure(self, _batch_id: str = "") -> None:
        async with self._cond:
            self.total_fail += 1
            self.success_streak = 0

    async def shrink(self, reason: str, batch_id: str = "") -> None:
        async with self._cond:
            old = self.cap
            self.cap = max(self.minimum, self.cap - ADAPTIVE_SHRINK_DELTA)
            self.success_streak = 0
            self.shrink_events += 1
            self._cond.notify_all()
        if old != self.cap:
            logger.warning(
                "[AdaptiveConcurrency] batch=%s 回撤(%s) cap %s→%s",
                batch_id,
                reason,
                old,
                self.cap,
            )

    def snapshot(self) -> dict[str, int]:
        return {
            "cap": self.cap,
            "active": self.active,
            "success_streak": self.success_streak,
            "total_success": self.total_success,
            "total_fail": self.total_fail,
            "grow_events": self.grow_events,
            "shrink_events": self.shrink_events,
        }


def _pool_cooldown_tick(
    last_known: float, get_cooldown_until: Callable[[], float]
) -> tuple[bool, float, float]:
    """返回 (是否新进入冷却, 剩余秒数, 当前冷却时间戳)。"""
    cd_until = float(get_cooldown_until())
    now = time.time()
    changed = cd_until > last_known + 0.5 and cd_until > now
    remain = max(0.0, cd_until - now)
    return changed, remain, cd_until


async def run_tdx_batch(  # noqa: PLR0915
    items: Sequence[T],
    process_one: Callable[[T], Awaitable[bool | None]],
    *,
    name: str = "tdx_batch",
    initial: int | None = None,
    minimum: int = ADAPTIVE_MIN,
    maximum: int = ADAPTIVE_MAX,
    burst_threshold: int = BATCH_FAIL_BURST_THRESHOLD,
    cooldown_seconds: int = BATCH_COOLDOWN_SECONDS,
    get_pool_cooldown_until: Callable[[], float] | None = None,
    cancel_check: Callable[[], bool] | None = None,
    log_summary: bool = True,
    runtime_stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """以自适应并发 + 批次熔断 + 池冷却联动执行批量 TDX 任务。"""
    total = len(items)
    if total == 0:
        return {
            "total": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "cap_final": 0,
            "grow_events": 0,
            "shrink_events": 0,
            "batch_cooldowns": 0,
            "pool_cooldowns": 0,
            "elapsed_s": 0.0,
        }

    gate = AdaptiveConcurrency(
        initial=initial if initial is not None else ADAPTIVE_INITIAL,
        minimum=minimum,
        maximum=maximum,
    )

    queue: asyncio.Queue[T] = asyncio.Queue()
    for it in items:
        queue.put_nowait(it)

    circuit: dict[str, int | float] = {
        "consec_fails": 0,
        "cooldown_until": 0.0,
        "last_known_pool_cd": 0.0,
        "batch_cooldowns": 0,
        "pool_cooldowns": 0,
        "skipped": 0,
    }
    circuit_lock = asyncio.Lock()
    start_ts = time.time()

    def _publish_runtime() -> None:
        if runtime_stats is None:
            return
        elapsed = time.time() - start_ts
        runtime_stats["elapsed_seconds"] = round(elapsed, 2)
        runtime_stats["gate"] = gate.snapshot()
        runtime_stats["batch_cooldown_until"] = float(circuit["cooldown_until"])
        pool_remain = 0.0
        if get_pool_cooldown_until is not None:
            pool_remain = max(0.0, get_pool_cooldown_until() - time.time())
        runtime_stats["pool_cooldown_remain_seconds"] = round(pool_remain, 1)

    logger.info(
        "[TdxBatchRunner] batch=%s items=%s cap_init=%s range=[%s,%s]",
        name,
        total,
        gate.cap,
        gate.minimum,
        gate.maximum,
    )

    async def _worker() -> None:
        while True:
            if cancel_check is not None and cancel_check():
                return
            now = time.time()
            wait_for = float(circuit["cooldown_until"]) - now
            if wait_for > 0:
                await asyncio.sleep(min(wait_for, 2.0))
                continue
            try:
                item = queue.get_nowait()
            except asyncio.QueueEmpty:
                return

            await gate.acquire()
            try:
                try:
                    result = await process_one(item)
                except Exception:
                    logger.exception("[TdxBatchRunner] batch=%s item=%r 异常", name, item)
                    result = False

                if result is None:
                    async with circuit_lock:
                        circuit["skipped"] = int(circuit["skipped"]) + 1
                elif result:
                    await gate.on_success(name)
                    async with circuit_lock:
                        if int(circuit["consec_fails"]) > 0:
                            circuit["consec_fails"] = 0
                else:
                    await gate.on_failure(name)
                    async with circuit_lock:
                        circuit["consec_fails"] = int(circuit["consec_fails"]) + 1
                        if (
                            int(circuit["consec_fails"]) >= burst_threshold
                            and time.time() >= float(circuit["cooldown_until"])
                        ):
                            circuit["cooldown_until"] = time.time() + cooldown_seconds
                            circuit["consec_fails"] = 0
                            circuit["batch_cooldowns"] = int(circuit["batch_cooldowns"]) + 1
                            log_ban_diagnostic(
                                "batch_burst",
                                extra={
                                    "batch_id": name,
                                    "threshold": burst_threshold,
                                    "cooldown_seconds": cooldown_seconds,
                                    "gate": gate.snapshot(),
                                },
                            )
                            logger.warning(
                                "[TdxBatchRunner] batch=%s 熔断: 连续 %s 失败, 暂停 %ss",
                                name,
                                burst_threshold,
                                cooldown_seconds,
                            )
                            await gate.shrink("batch_burst", name)

                if get_pool_cooldown_until is not None:
                    changed, remain, cd_until = _pool_cooldown_tick(
                        float(circuit["last_known_pool_cd"]),
                        get_pool_cooldown_until,
                    )
                    if cd_until > float(circuit["last_known_pool_cd"]):
                        circuit["last_known_pool_cd"] = cd_until
                    if changed:
                        async with circuit_lock:
                            circuit["cooldown_until"] = max(
                                float(circuit["cooldown_until"]),
                                time.time() + remain,
                            )
                            circuit["pool_cooldowns"] = int(circuit["pool_cooldowns"]) + 1
                        await gate.shrink("pool_global_cooldown", name)
                        logger.warning(
                            "[TdxBatchRunner] batch=%s 池全局冷却剩余约 %ss, gate=%s",
                            name,
                            int(remain),
                            gate.cap,
                        )
            finally:
                await gate.release()
                _publish_runtime()
                queue.task_done()

    workers = [asyncio.create_task(_worker()) for _ in range(gate.maximum)]
    await asyncio.gather(*workers, return_exceptions=True)

    elapsed = time.time() - start_ts
    summary = {
        "total": total,
        "success": gate.total_success,
        "failed": gate.total_fail,
        "skipped": int(circuit["skipped"]),
        "cap_final": gate.cap,
        "grow_events": gate.grow_events,
        "shrink_events": gate.shrink_events,
        "batch_cooldowns": int(circuit["batch_cooldowns"]),
        "pool_cooldowns": int(circuit["pool_cooldowns"]),
        "elapsed_s": round(elapsed, 2),
    }
    if log_summary:
        logger.info(
            "[TdxBatchRunner] batch=%s 完成 total=%s ok=%s fail=%s skip=%s "
            "cap=%s grow=%s shrink=%s batch_cd=%s pool_cd=%s elapsed=%ss",
            name,
            summary["total"],
            summary["success"],
            summary["failed"],
            summary["skipped"],
            summary["cap_final"],
            summary["grow_events"],
            summary["shrink_events"],
            summary["batch_cooldowns"],
            summary["pool_cooldowns"],
            summary["elapsed_s"],
        )
    return summary
