"""API 进程配置（CORS、运行环境）。"""
from __future__ import annotations

import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="IQUANT_", extra="ignore")

    env: str = Field(default="local")
    api_error_log_path: str = Field(
        default="logs/iquant-api-errors.log",
        description="API 进程 ERROR 级滚动日志路径（相对当前工作目录）",
    )
    client_error_log_path: str = Field(
        default="logs/iquant-admin-web-errors.log",
        description="管理端上报的前端错误 JSONL 路径",
    )
    cors_origins: str = Field(
        default="*",
        description="逗号分隔的 CORS 白名单；* 表示开发期放开",
    )
    admin_web_origin: str = Field(
        default="",
        description="生产环境管理后台 Origin，用于 CORS 与 Turnstile 展示",
    )


_settings: ApiSettings | None = None


def get_api_settings() -> ApiSettings:
    global _settings
    if _settings is None:
        _settings = ApiSettings()
    return _settings


def is_production() -> bool:
    return get_api_settings().env.lower() in ("prod", "production")


def cors_allow_origins() -> list[str]:
    s = get_api_settings()
    raw = (s.cors_origins or "").strip()
    if raw == "*" or not raw:
        if is_production() and s.admin_web_origin:
            return [s.admin_web_origin]
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


def docs_enabled() -> bool:
    return os.environ.get("IQUANT_OPENAPI_ENABLED", "").lower() in (
        "1",
        "true",
        "yes",
    ) or not is_production()
