"""身份服务配置。"""
from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 开发容器内仓库挂载在 /workspace；本地直接跑时用当前工作目录
_WORKSPACE = Path(os.environ.get("IQUANT_WORKSPACE", "/workspace"))
if not (_WORKSPACE / ".env").is_file():
    _WORKSPACE = Path.cwd()


class IdentitySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="IQUANT_",
        env_file=_WORKSPACE / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 环境变量名：IQUANT_PG_DSN / IQUANT_REDIS_URL（勿用 validation_alias 短名，否则 env_prefix 不生效）
    pg_dsn: str = Field(
        default="postgresql+asyncpg://iquant:iquant_dev_pwd@postgres:5432/iquant",
    )
    redis_url: str = Field(default="redis://redis:6379/0")

    admin_jwt_secret: str = Field(default="dev-change-me-admin-jwt-secret")
    admin_access_token_minutes: int = Field(default=15)
    admin_refresh_token_days: int = Field(default=30)

    turnstile_secret: str = Field(default="")
    turnstile_site_key: str = Field(default="")

    admin_bootstrap_username: str = Field(default="admin")
    admin_bootstrap_password: str = Field(default="")

    login_rate_limit_per_minute: int = Field(default=5)
    login_fail_lock_threshold: int = Field(default=10)
    login_fail_lock_seconds: int = Field(default=900)
    admin_api_rate_limit_per_minute: int = Field(default=120)
    anonymous_admin_rate_limit_per_minute: int = Field(default=20)

    sse_ticket_seconds: int = Field(default=60)


_settings: IdentitySettings | None = None


def get_identity_settings() -> IdentitySettings:
    global _settings
    if _settings is None:
        _settings = IdentitySettings()
    return _settings
