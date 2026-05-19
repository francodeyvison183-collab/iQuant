"""行为策略 DSL Pydantic 模型（MVP v1）。"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1"
TemplateId = Literal["ma_breakout", "pullback_ma", "trend_hold"]
RuleType = Literal["cross_above", "cross_below", "hold_days_max"]
IndicatorId = Literal["ma", "close"]


class IndicatorRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    indicator: IndicatorId
    params: dict[str, Any] = Field(default_factory=dict)


class RuleClause(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: RuleType
    left: IndicatorRef
    right: IndicatorRef | None = None
    value: Decimal | None = None


class RiskBlock(BaseModel):
    model_config = ConfigDict(frozen=True)

    stop_loss_pct: Decimal | None = Field(default=None, ge=0, le=1)
    take_profit_pct: Decimal | None = Field(default=None, ge=0, le=1)
    max_hold_days: int | None = Field(default=None, ge=1, le=500)


class StrategyMeta(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str = "blind_replay"
    template_id: TemplateId
    fit_score: float = Field(ge=0, le=1)
    blind_session_count: int = Field(ge=0)


class BehaviorStrategyDSL(BaseModel):
    """可回测的行为策略 DSL 文档。"""

    model_config = ConfigDict(frozen=True)

    schema_version: str = SCHEMA_VERSION
    name: str = Field(min_length=1, max_length=128)
    period: str = Field(default="day", max_length=16)
    market_side: Literal["long_only"] = "long_only"
    entry: RuleClause
    exit: RuleClause
    risk: RiskBlock = Field(default_factory=RiskBlock)
    meta: StrategyMeta
