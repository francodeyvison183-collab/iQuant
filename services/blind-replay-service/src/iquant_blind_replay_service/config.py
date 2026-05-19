"""盲测回放服务配置（业务主库）。"""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BlindReplaySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="IQUANT_", extra="ignore")

    pg_dsn: str = Field(
        default="postgresql+asyncpg://iquant:iquant_dev_pwd@postgres:5432/iquant",
    )
    default_months_back: int = Field(default=6, ge=1, le=24)
    chart_visible_max_bars: int = Field(default=160, ge=30, le=500)
    warmup_bars: int = Field(default=20, ge=5, le=60)
    min_bars_in_range: int = Field(default=40, ge=20, le=200)
    required_trade_actions: int = Field(default=10, ge=1, le=50)
    consistency_min_sessions: int = Field(default=3, ge=3, le=20)
    consistency_ready_threshold: int = Field(default=60, ge=0, le=100)


_settings: BlindReplaySettings | None = None


def get_blind_replay_settings() -> BlindReplaySettings:
    global _settings
    if _settings is None:
        _settings = BlindReplaySettings()
    return _settings
