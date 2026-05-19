"""Redis 客户端（限流、JWT 吊销、SSE ticket）。"""
from __future__ import annotations

import json
import time
from typing import Any

from redis.asyncio import Redis

from .config import get_identity_settings

_client: Redis | None = None


async def get_redis() -> Redis:
    global _client
    if _client is None:
        _client = Redis.from_url(get_identity_settings().redis_url, decode_responses=True)
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def rate_limit_hit(*, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
    """滑动窗口计数；返回 (是否允许, retry_after_seconds)。"""
    r = await get_redis()
    now = int(time.time())
    bucket = f"rl:{key}:{now // window_seconds}"
    count = await r.incr(bucket)
    if count == 1:
        await r.expire(bucket, window_seconds + 1)
    if count > limit:
        ttl = await r.ttl(bucket)
        return False, max(int(ttl), 1)
    return True, 0


async def is_ip_locked(ip: str) -> tuple[bool, int]:
    r = await get_redis()
    ttl = await r.ttl(f"admin:login:lock:{ip}")
    if ttl and ttl > 0:
        return True, int(ttl)
    return False, 0


async def record_login_failure(ip: str, *, threshold: int, lock_seconds: int) -> None:
    r = await get_redis()
    key = f"admin:login:fail:{ip}"
    count = await r.incr(key)
    if count == 1:
        await r.expire(key, lock_seconds)
    if count >= threshold:
        await r.setex(f"admin:login:lock:{ip}", lock_seconds, "1")


async def clear_login_failures(ip: str) -> None:
    r = await get_redis()
    await r.delete(f"admin:login:fail:{ip}", f"admin:login:lock:{ip}")


async def revoke_access_jti(jti: str, ttl_seconds: int) -> None:
    if ttl_seconds <= 0:
        return
    r = await get_redis()
    await r.setex(f"admin:jwt:revoked:{jti}", ttl_seconds, "1")


async def is_access_jti_revoked(jti: str) -> bool:
    r = await get_redis()
    return bool(await r.exists(f"admin:jwt:revoked:{jti}"))


async def issue_sse_ticket(*, admin_user_id: int, task_id: str, ttl_seconds: int) -> str:
    import secrets

    ticket = secrets.token_urlsafe(24)
    r = await get_redis()
    payload = json.dumps({"admin_user_id": admin_user_id, "task_id": task_id})
    await r.setex(f"admin:sse:ticket:{ticket}", ttl_seconds, payload)
    return ticket


async def consume_sse_ticket(ticket: str, *, task_id: str) -> int | None:
    r = await get_redis()
    key = f"admin:sse:ticket:{ticket}"
    raw = await r.getdel(key)
    if not raw:
        return None
    data: dict[str, Any] = json.loads(raw)
    if data.get("task_id") != task_id:
        return None
    return int(data["admin_user_id"])
