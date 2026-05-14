"""TDX 连接池：同步 TCP 客户端 + asyncio 封装。

对齐 ``HQScanner`` 的反封禁经验：
- 并发上限与连接数与 ``AdaptiveConcurrency.maximum`` 一致，``max_size`` 钳制到 ≤8。
- 全局冷却：连接连续失败 / 单页多次换线仍空 时进入 60s 窗口，避免 IP 被协同拉黑。
- 区间分页拉取：首页按交易日粗估 ``count``；页间 ``0.25s``；单页空响应先 ``1.5s`` 原连接重试再换线。
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import datetime
from typing import TypeVar

from iquant_domain.errors import TdxGlobalCooldown, TdxHostUnavailable, TdxProtocolError
from iquant_domain.market import KlinePeriod, MarketBar, MarketBarBatch

from .ban_diagnostic import log_ban_diagnostic, record_failure, record_request
from .client import TdxClient
from .host_manager import TdxHost, TdxHostManager
from .range_estimate import TDX_PAGE_SIZE, estimate_first_page_count

logger = logging.getLogger(__name__)

T = TypeVar("T")

# 与 HQScanner ``_PYTDX_KLINE_*`` / ``tdx_batch_runner`` 对齐
_POOL_HARD_CAP = 8
_COOLDOWN_SECONDS = 60
_CONNECT_FAIL_STREAK = 3
_PAGE_FAIL_STREAK = 3


class TdxConnectionPool:
    """TDX 连接池：``max_size`` 同时是并发连接上限，且不超过 8。"""

    def __init__(
        self,
        host_manager: TdxHostManager,
        *,
        max_size: int = 4,
        connect_timeout: float = 5.0,
        read_timeout: float = 10.0,
    ) -> None:
        self._hm = host_manager
        raw = max(1, max_size)
        if raw > _POOL_HARD_CAP:
            logger.warning(
                "tdx_pool_size_clamped",
                extra={"requested": raw, "clamped_to": _POOL_HARD_CAP},
            )
        self._max_size = min(raw, _POOL_HARD_CAP)
        self._connect_timeout = connect_timeout
        self._read_timeout = read_timeout
        self._idle: asyncio.LifoQueue[TdxClient] = asyncio.LifoQueue(maxsize=self._max_size)
        self._sem = asyncio.Semaphore(self._max_size)
        self._lock = asyncio.Lock()
        self._round_robin = 0
        self._global_cooldown_until = 0.0
        self._connect_fail_streak = 0
        self._page_fail_streak = 0
        self._cooldown_lock = asyncio.Lock()

    @property
    def global_cooldown_until(self) -> float:
        """供 ``run_tdx_batch`` 检测池级冷却（与 HQScanner 导出变量语义一致）。"""
        return self._global_cooldown_until

    @property
    def max_size(self) -> int:
        return self._max_size

    async def _enter_global_cooldown(self, reason: str, *, extra: dict | None = None) -> None:
        async with self._cooldown_lock:
            self._global_cooldown_until = time.time() + _COOLDOWN_SECONDS
            payload = {"pool_max": self._max_size, **(extra or {})}
        log_ban_diagnostic(reason, extra=payload)
        logger.warning(
            "tdx_pool_global_cooldown",
            extra={"reason": reason, "seconds": _COOLDOWN_SECONDS},
        )

    def _check_cooldown(self) -> None:
        now = time.time()
        if now < self._global_cooldown_until:
            rem = int(self._global_cooldown_until - now)
            raise TdxGlobalCooldown(f"TDX 全局冷却中，约 {rem}s 后再试")

    async def _note_connect_ok(self) -> None:
        async with self._cooldown_lock:
            self._connect_fail_streak = 0

    async def _note_connect_fail(self) -> None:
        async with self._cooldown_lock:
            self._connect_fail_streak += 1
            if self._connect_fail_streak >= _CONNECT_FAIL_STREAK:
                self._connect_fail_streak = 0
                self._global_cooldown_until = time.time() + _COOLDOWN_SECONDS
                should_log = True
            else:
                should_log = False
        if should_log:
            log_ban_diagnostic(
                "connect_streak",
                extra={"threshold": _CONNECT_FAIL_STREAK, "cooldown_seconds": _COOLDOWN_SECONDS},
            )
            logger.warning("tdx_connect_streak_cooldown", extra={"seconds": _COOLDOWN_SECONDS})

    async def _note_page_catastrophe(self) -> None:
        async with self._cooldown_lock:
            self._page_fail_streak += 1
            if self._page_fail_streak >= _PAGE_FAIL_STREAK:
                self._page_fail_streak = 0
                self._global_cooldown_until = time.time() + _COOLDOWN_SECONDS
                should_log = True
            else:
                should_log = False
        if should_log:
            log_ban_diagnostic(
                "page_fetch_streak",
                extra={"threshold": _PAGE_FAIL_STREAK, "cooldown_seconds": _COOLDOWN_SECONDS},
            )

    async def _note_page_ok(self) -> None:
        async with self._cooldown_lock:
            self._page_fail_streak = 0

    @asynccontextmanager
    async def acquire(self):  # type: ignore[no-untyped-def]
        self._check_cooldown()
        await self._sem.acquire()
        client: TdxClient | None = None
        try:
            client = self._idle.get_nowait() if not self._idle.empty() else None
            if client is None:
                client = await self._create_client()
            yield client
        except Exception:
            if client is not None:
                client.close()
                client = None
            raise
        finally:
            if client is not None and client.connected:
                try:
                    self._idle.put_nowait(client)
                except asyncio.QueueFull:
                    client.close()
            self._sem.release()

    async def run_sync(self, fn: Callable[[TdxClient], T]) -> T:
        loop = asyncio.get_running_loop()
        async with self.acquire() as client:
            return await loop.run_in_executor(None, fn, client)

    async def run_sync_with_retry(
        self,
        fn: Callable[[TdxClient], T],
        *,
        retries: int = 2,
    ) -> T:
        last_exc: Exception | None = None
        for attempt in range(retries + 1):
            try:
                return await self.run_sync(fn)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning(
                    "tdx_call_retry",
                    extra={"attempt": attempt, "error": str(exc)},
                )
        assert last_exc is not None
        raise last_exc

    async def fetch_bars_in_range_resilient(  # noqa: PLR0915
        self,
        *,
        full_code: str,
        period: KlinePeriod,
        start: datetime,
        end: datetime | None = None,
        hard_max_bars: int = 20000,
    ) -> MarketBarBatch:
        """按区间分页拉取 K 线（HQScanner ``fetch_kline_paged`` 策略的 iQuant 实现）。"""
        end_dt = end if end is not None else datetime.now()
        if start.tzinfo is not None or end_dt.tzinfo is not None:
            start = start.replace(tzinfo=None)  # type: ignore[assignment]
            end_dt = end_dt.replace(tzinfo=None)  # type: ignore[assignment]

        first_page_count = estimate_first_page_count(period=period, start=start, end=end_dt)
        all_bars: list[MarketBar] = []
        seen: set[datetime] = set()
        offset = 0
        first_page = True
        loop = asyncio.get_running_loop()

        while len(all_bars) < hard_max_bars and offset < hard_max_bars:
            page_count = first_page_count if first_page else TDX_PAGE_SIZE
            first_page = False
            page_rows: list[MarketBar] | None = None

            for _conn_round in range(3):
                self._check_cooldown()
                async with self.acquire() as client:
                    host_key = (client.host, client.port)
                    last_batch: MarketBarBatch | None = None
                    for soft in range(2):
                        try:

                            def _one_fetch(
                                c: TdxClient = client,
                                o: int = offset,
                                pc: int = page_count,
                            ) -> MarketBarBatch:
                                return c.fetch_bars(
                                    full_code=full_code,
                                    period=period,
                                    offset=o,
                                    count=pc,
                                )

                            last_batch = await loop.run_in_executor(None, _one_fetch)
                        except TdxProtocolError as exc:
                            record_failure(
                                code=full_code,
                                host_key=host_key,
                                exc_cls=type(exc).__name__,
                                msg=str(exc),
                                is_empty=False,
                            )
                            client.close()
                            last_batch = None
                            break
                        record_request(host_key)
                        if last_batch is not None and not last_batch.is_empty:
                            page_rows = list(last_batch.bars)
                            break
                        record_failure(
                            code=full_code,
                            host_key=host_key,
                            exc_cls="EmptyResponse",
                            msg=f"empty soft={soft}",
                            is_empty=True,
                        )
                        if soft == 0:
                            await asyncio.sleep(1.5)
                    if page_rows:
                        break
                    if client.connected:
                        client.close()
                if page_rows:
                    break

            if not page_rows:
                await self._note_page_catastrophe()
                break

            await self._note_page_ok()

            new_added = 0
            for bar in page_rows:
                if bar.bar_time in seen:
                    continue
                seen.add(bar.bar_time)
                all_bars.append(bar)
                new_added += 1

            oldest = min((b.bar_time for b in page_rows), default=None)
            newest = max((b.bar_time for b in page_rows), default=None)

            if oldest is not None and oldest <= start:
                break
            if newest is not None and newest < start:
                break
            if new_added == 0:
                break
            if len(page_rows) < page_count:
                break

            offset += page_count
            await asyncio.sleep(0.25 + random.random() * 0.05)

        filtered = [b for b in all_bars if start <= b.bar_time <= end_dt]
        filtered.sort(key=lambda b: b.bar_time)
        return MarketBarBatch(full_code=full_code, period=period, bars=filtered)

    async def _create_client(self) -> TdxClient:
        async with self._lock:
            host = self._pick_host()
        loop = asyncio.get_running_loop()
        client = TdxClient(
            host.ip,
            host.port,
            connect_timeout=self._connect_timeout,
            read_timeout=self._read_timeout,
        )
        try:
            await loop.run_in_executor(None, client.connect)
        except Exception:
            client.close()
            await self._note_connect_fail()
            raise
        await self._note_connect_ok()
        return client

    def _pick_host(self) -> TdxHost:
        hosts = self._hm.available()
        if not hosts:
            raise TdxHostUnavailable("当前没有可用 TDX 主站，请先在管理界面测速")
        host = hosts[self._round_robin % len(hosts)]
        self._round_robin += 1
        return host

    async def close(self) -> None:
        while not self._idle.empty():
            try:
                c = self._idle.get_nowait()
            except asyncio.QueueEmpty:
                break
            c.close()
