"""Cloudflare Turnstile 校验；未配置 secret 时开发环境跳过。"""
from __future__ import annotations

import httpx
import structlog

from .config import get_identity_settings

logger = structlog.get_logger(__name__)


async def verify_turnstile(*, token: str, remote_ip: str | None) -> bool:
    settings = get_identity_settings()
    if not settings.turnstile_secret:
        return True
    if not token:
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data={
                    "secret": settings.turnstile_secret,
                    "response": token,
                    "remoteip": remote_ip or "",
                },
            )
        data = resp.json()
        return bool(data.get("success"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("turnstile_verify_failed", error=str(exc))
        return False
