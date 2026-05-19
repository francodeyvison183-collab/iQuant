"""管理端写操作审计（登录失败由 identity 用例单独记录）。"""
from __future__ import annotations

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from iquant_identity_service.usecases.audit import append_audit_log
from iquant_identity_service.usecases.auth import verify_access_token

from ..deps import client_ip, request_id, user_agent

logger = structlog.get_logger(__name__)

_SKIP_SUFFIXES = ("/login", "/refresh", "/logout")


class AdminAuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        path = request.url.path
        if not path.startswith("/api/v1/admin"):
            return response
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return response
        if any(path.endswith(s) for s in _SKIP_SUFFIXES):
            return response

        admin_id: int | None = None
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            try:
                profile = await verify_access_token(auth[7:].strip())
                admin_id = profile.id
            except Exception:  # noqa: BLE001
                pass
        elif hasattr(request.state, "admin"):
            admin_id = request.state.admin.id

        action = f"admin.api.{request.method.lower()}"
        try:
            await append_audit_log(
                admin_user_id=admin_id,
                action=action,
                method=request.method,
                path=path,
                status_code=response.status_code,
                ip=client_ip(request),
                user_agent=user_agent(request),
                request_id=request_id(request),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("admin_audit_append_failed", path=path, error=str(exc))
        return response
