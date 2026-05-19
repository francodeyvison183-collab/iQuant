"""策略 API schema。"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StrategyGenerateIn(BaseModel):
    model_config = ConfigDict(frozen=True)

    period: str | None = Field(default=None, max_length=16)
    consistency_report_id: UUID | None = None


class StrategyVersionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    version_no: int
    status: str
    dsl: dict[str, Any]
    rules_summary: list[str]
    rank_score: str
    is_selected: bool
    created_at: datetime
    confirmed_at: datetime | None


class StrategyOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    name: str
    status: str
    source: str
    period: str
    consistency_report_id: UUID | None
    created_at: datetime
    updated_at: datetime
    versions: list[StrategyVersionOut]


class StrategySummaryOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    name: str
    status: str
    period: str
    version_count: int
    confirmed_version_id: UUID | None
    created_at: datetime


class StrategyConfirmIn(BaseModel):
    model_config = ConfigDict(frozen=True)

    version_id: UUID
