"""回测服务配置。"""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BacktestSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="IQUANT_", extra="ignore")

    pg_dsn: str = Field(
        default="postgresql+asyncpg://iquant:iquant_dev_pwd@postgres:5432/iquant",
    )


_settings: BacktestSettings | None = None


def get_backtest_settings() -> BacktestSettings:
    global _settings
    if _settings is None:
        _settings = BacktestSettings()
    return _settings
