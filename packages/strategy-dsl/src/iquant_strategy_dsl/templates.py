"""内置策略模板（与 blind 特征分布匹配）。"""
from __future__ import annotations

from decimal import Decimal

from .models import (
    BehaviorStrategyDSL,
    IndicatorRef,
    RiskBlock,
    RuleClause,
    StrategyMeta,
    TemplateId,
)


def build_template_dsl(
    *,
    template_id: TemplateId,
    name: str,
    period: str,
    fit_score: float,
    blind_session_count: int,
    entry_ma: int = 20,
    exit_ma: int = 10,
    max_hold_days: int | None = None,
    stop_loss_pct: Decimal | None = Decimal("0.08"),
) -> BehaviorStrategyDSL:
    """按模板生成 DSL 实例。"""
    if template_id == "ma_breakout":
        entry = RuleClause(
            type="cross_above",
            left=IndicatorRef(indicator="close"),
            right=IndicatorRef(indicator="ma", params={"period": entry_ma}),
        )
        exit_clause = RuleClause(
            type="cross_below",
            left=IndicatorRef(indicator="close"),
            right=IndicatorRef(indicator="ma", params={"period": exit_ma}),
        )
        risk = RiskBlock(stop_loss_pct=stop_loss_pct, max_hold_days=max_hold_days)
    elif template_id == "pullback_ma":
        entry = RuleClause(
            type="cross_above",
            left=IndicatorRef(indicator="close"),
            right=IndicatorRef(indicator="ma", params={"period": entry_ma}),
        )
        exit_clause = RuleClause(
            type="cross_below",
            left=IndicatorRef(indicator="close"),
            right=IndicatorRef(indicator="ma", params={"period": exit_ma}),
        )
        risk = RiskBlock(stop_loss_pct=stop_loss_pct or Decimal("0.06"), max_hold_days=max_hold_days or 30)
    else:
        entry = RuleClause(
            type="cross_above",
            left=IndicatorRef(indicator="ma", params={"period": entry_ma}),
            right=IndicatorRef(indicator="ma", params={"period": exit_ma}),
        )
        exit_clause = RuleClause(
            type="hold_days_max",
            left=IndicatorRef(indicator="close"),
            value=Decimal(str(max_hold_days or 40)),
        )
        risk = RiskBlock(stop_loss_pct=stop_loss_pct, max_hold_days=max_hold_days or 40)

    return BehaviorStrategyDSL(
        name=name,
        period=period,
        entry=entry,
        exit=exit_clause,
        risk=risk,
        meta=StrategyMeta(
            source="blind_replay",
            template_id=template_id,
            fit_score=fit_score,
            blind_session_count=blind_session_count,
        ),
    )


TEMPLATE_LABELS: dict[TemplateId, str] = {
    "ma_breakout": "均线突破型",
    "pullback_ma": "回调靠近均线",
    "trend_hold": "趋势持有型",
}
