"""策略服务配置。"""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class StrategySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="IQUANT_", extra="ignore")

    pg_dsn: str = Field(
        default="postgresql+asyncpg://iquant:iquant_dev_pwd@postgres:5432/iquant",
    )
    max_candidates: int = Field(default=3, ge=1, le=5)


_settings: StrategySettings | None = None


def get_strategy_settings() -> StrategySettings:
    global _settings
    if _settings is None:
        _settings = StrategySettings()
    return _settings
