"""TDX 连接池：将同步 TCP 客户端封装成可在 asyncio 中复用的连接池。

设计要点：
- 连接懒创建；获取连接时如果池里没有空闲连接则新建并落到不同主站，分散压力。
- 使用 ``asyncio.Lock`` 控制并发上限；获取连接的协程在线程池里完成同步 I/O。
- 连接被异常关闭后下次会自动重连，调用方无需感知。
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import TypeVar

from iquant_domain.errors import TdxHostUnavailable

from .client import TdxClient
from .host_manager import TdxHost, TdxHostManager

logger = logging.getLogger(__name__)

T = TypeVar("T")


class TdxConnectionPool:
    """轻量 TDX 连接池。

    ``max_size`` 同时也是允许的并发连接上限。
    """

    def __init__(
        self,
        host_manager: TdxHostManager,
        *,
        max_size: int = 4,
        connect_timeout: float = 5.0,
        read_timeout: float = 10.0,
    ) -> None:
        self._hm = host_manager
        self._max_size = max_size
        self._connect_timeout = connect_timeout
        self._read_timeout = read_timeout
        self._idle: asyncio.LifoQueue[TdxClient] = asyncio.LifoQueue(maxsize=max_size)
        self._sem = asyncio.Semaphore(max_size)
        self._lock = asyncio.Lock()
        self._round_robin = 0

    # ── 取/放连接 ─────────────────────────────────────────────────────────────

    @asynccontextmanager
    async def acquire(self):  # type: ignore[no-untyped-def]
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
        """在连接池中以同步方式执行函数，自动落入 default executor。"""
        loop = asyncio.get_running_loop()
        async with self.acquire() as client:
            return await loop.run_in_executor(None, fn, client)

    async def run_sync_with_retry(
        self,
        fn: Callable[[TdxClient], T],
        *,
        retries: int = 2,
    ) -> T:
        """带重试的 run_sync，遇到协议/网络异常会切换连接重试。"""
        last_exc: Exception | None = None
        for attempt in range(retries + 1):
            try:
                return await self.run_sync(fn)
            except Exception as exc:  # noqa: BLE001 - 池内连接失败要整体重试
                last_exc = exc
                logger.warning(
                    "tdx_call_retry",
                    extra={"attempt": attempt, "error": str(exc)},
                )
        assert last_exc is not None
        raise last_exc

    # ── 内部 ─────────────────────────────────────────────────────────────────

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
            raise
        return client

    def _pick_host(self) -> TdxHost:
        hosts = self._hm.available()
        if not hosts:
            raise TdxHostUnavailable("当前没有可用 TDX 主站，请先在管理界面测速")
        # 轮询分散到不同主站
        host = hosts[self._round_robin % len(hosts)]
        self._round_robin += 1
        return host

    async def close(self) -> None:
        while not self._idle.empty():
            try:
                client = self._idle.get_nowait()
            except asyncio.QueueEmpty:
                break
            client.close()
