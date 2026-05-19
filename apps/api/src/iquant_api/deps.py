"""FastAPI 依赖：客户端信息、管理员鉴权。"""
from __future__ import annotations

from fastapi import Header, Request

from iquant_domain.errors import AuthError
from iquant_identity_service.usecases.auth import verify_access_token
from iquant_identity_service.usecases.schemas import AdminProfile


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return ""


def user_agent(request: Request) -> str:
    return (request.headers.get("user-agent") or "")[:512]


def request_id(request: Request) -> str:
    return (request.headers.get("x-request-id") or request.headers.get("x-correlation-id") or "")[
        :64
    ]


async def require_admin(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> AdminProfile:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthError("请先登录", code="AUTH_REQUIRED")
    token = authorization[7:].strip()
    if not token:
        raise AuthError("请先登录", code="AUTH_REQUIRED")
    profile = await verify_access_token(token)
    request.state.admin = profile
    return profile
