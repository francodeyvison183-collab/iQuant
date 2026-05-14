"""任务进度事件总线。

SSE 在 API 进程内消费，事件由 worker 进程产生，需要跨进程通道：使用 Redis pub/sub。
"""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from redis.asyncio import Redis

from .config import get_market_settings

logger = logging.getLogger(__name__)

_PREFIX = "iquant:market:progress:"


def _channel(task_id: str) -> str:
    return f"{_PREFIX}{task_id}"


async def get_redis() -> Redis:
    return Redis.from_url(get_market_settings().redis_url, decode_responses=True)


async def publish(task_id: str, event_type: str, payload: dict) -> None:
    """worker 侧发布事件。"""
    r = await get_redis()
    try:
        await r.publish(
            _channel(task_id),
            json.dumps({"type": event_type, "data": payload}, ensure_ascii=False),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("progress_publish_failed", extra={"task_id": task_id, "error": str(exc)})
    finally:
        await r.aclose()


@asynccontextmanager
async def subscribe(task_id: str) -> AsyncIterator[AsyncIterator[dict]]:
    """API 侧订阅。退出 with 时自动 unsubscribe。"""
    r = await get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe(_channel(task_id))

    async def _iter() -> AsyncIterator[dict]:
        async for msg in pubsub.listen():
            if msg.get("type") != "message":
                continue
            try:
                yield json.loads(msg["data"])
            except json.JSONDecodeError:
                continue

    try:
        yield _iter()
    finally:
        try:
            await pubsub.unsubscribe(_channel(task_id))
        finally:
            await pubsub.close()
            await r.aclose()
