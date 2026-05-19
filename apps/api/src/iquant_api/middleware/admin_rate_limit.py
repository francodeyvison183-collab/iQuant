"""管理端 API 全局限流。"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from iquant_domain.errors import RateLimitedError, ServiceUnavailableError
from redis.exceptions import RedisError
from iquant_identity_service.config import get_identity_settings
from iquant_identity_service.redis_client import rate_limit_hit
from iquant_identity_service.usecases.auth import verify_access_token


class AdminRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if not path.startswith("/api/v1/admin"):
            return await call_next(request)

        settings = get_identity_settings()
        ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if not ip and request.client:
            ip = request.client.host

        limit = settings.anonymous_admin_rate_limit_per_minute
        key_suffix = f"anon:{ip}"

        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            try:
                profile = await verify_access_token(auth[7:].strip())
                limit = settings.admin_api_rate_limit_per_minute
                key_suffix = f"user:{profile.id}"
            except Exception:  # noqa: BLE001
                pass

        try:
            allowed, retry = await rate_limit_hit(
                key=f"admin:api:{key_suffix}",
                limit=limit,
                window_seconds=60,
            )
        except RedisError:
            err = ServiceUnavailableError(
                "服务暂不可用（Redis），请确认 docker compose 已启动 redis 服务"
            )
            return JSONResponse(
                status_code=503,
                content={"error": {"code": err.code, "message": err.message}},
            )
        if not allowed:
            exc = RateLimitedError(f"请求过于频繁，请 {retry} 秒后再试")
            return JSONResponse(
                status_code=429,
                content={"error": {"code": exc.code, "message": exc.message}},
            )

        return await call_next(request)
