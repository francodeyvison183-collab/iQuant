"""管理员鉴权 REST。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, Field

from iquant_identity_service.config import get_identity_settings
from iquant_identity_service.usecases import auth as auth_uc
from iquant_identity_service.usecases.schemas import AdminProfile

from ...deps import client_ip, require_admin, user_agent

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)
    captcha_token: str = Field(default="")


class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=16)


class LogoutIn(BaseModel):
    refresh_token: str = Field(min_length=16)


class ChangePasswordIn(BaseModel):
    old_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)


@router.get("/config")
async def api_auth_config() -> dict:
    settings = get_identity_settings()
    return {
        "code": 0,
        "data": {
            "turnstile_site_key": settings.turnstile_site_key,
            "turnstile_required": bool(settings.turnstile_secret),
        },
    }


@router.post("/login")
async def api_login(body: LoginIn, request: Request) -> dict:
    result = await auth_uc.login(
        username=body.username,
        password=body.password,
        ip=client_ip(request),
        user_agent=user_agent(request),
        captcha_token=body.captcha_token,
    )
    return {"code": 0, "data": result.model_dump(mode="json")}


@router.post("/refresh")
async def api_refresh(body: RefreshIn, request: Request) -> dict:
    result = await auth_uc.refresh_session(
        refresh_token=body.refresh_token,
        ip=client_ip(request),
        user_agent=user_agent(request),
    )
    return {"code": 0, "data": result.model_dump(mode="json")}


@router.post("/logout")
async def api_logout(
    body: LogoutIn,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict:
    access = None
    if authorization and authorization.lower().startswith("bearer "):
        access = authorization[7:].strip()
    await auth_uc.logout(refresh_token=body.refresh_token, access_token=access)
    return {"code": 0, "message": "已退出"}


@router.get("/me")
async def api_me(admin: AdminProfile = Depends(require_admin)) -> dict:
    return {"code": 0, "data": admin.model_dump(mode="json")}


@router.patch("/password")
async def api_change_password(
    body: ChangePasswordIn,
    admin: AdminProfile = Depends(require_admin),
) -> dict:
    await auth_uc.change_password(
        admin_id=admin.id,
        old_password=body.old_password,
        new_password=body.new_password,
    )
    return {"code": 0, "message": "密码已更新"}
