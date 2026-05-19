"""标注服务配置（业务主库，与行情元数据同库）。"""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AnnotationSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="IQUANT_", extra="ignore")

    pg_dsn: str = Field(
        default="postgresql+asyncpg://iquant:iquant_dev_pwd@postgres:5432/iquant",
    )


_settings: AnnotationSettings | None = None


def get_annotation_settings() -> AnnotationSettings:
    global _settings
    if _settings is None:
        _settings = AnnotationSettings()
    return _settings
