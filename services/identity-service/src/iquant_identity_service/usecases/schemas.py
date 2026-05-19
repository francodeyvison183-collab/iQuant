"""身份服务用例 schema。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AdminProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    username: str
    display_name: str
    must_change_password: bool
    last_login_at: datetime | None


class LoginResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    access_token: str
    refresh_token: str
    expires_at: datetime
    admin: AdminProfile


class AuditLogRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    admin_user_id: int | None
    username: str | None
    action: str
    resource_type: str
    resource_id: str
    method: str
    path: str
    status_code: int
    ip: str
    user_agent: str
    request_id: str
    detail: dict
    created_at: datetime


class SseTicketResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    ticket: str
    expires_in: int = Field(description="秒")
