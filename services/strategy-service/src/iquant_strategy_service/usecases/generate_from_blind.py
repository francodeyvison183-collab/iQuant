"""从盲测样本归纳候选 DSL（规则引擎，禁止 label_* 输入）。"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from statistics import median
from iquant_strategy_dsl import (
    BehaviorStrategyDSL,
    TemplateId,
    build_template_dsl,
    dsl_to_rule_lines,
    validate_dsl,
)

from iquant_blind_replay_service.usecases.consistency_profile import SessionActionSample


@dataclass(frozen=True)
class StrategyCandidateDraft:
    template_id: TemplateId
    name: str
    dsl: BehaviorStrategyDSL
    rules_summary: list[str]
    rank_score: Decimal


def _buy_ma_distances(samples: list[SessionActionSample]) -> list[float]:
    out: list[float] = []
    for s in samples:
        for _, action, feat in s.actions:
            if action != "buy":
                continue
            d = feat.get("ma20_dist")
            if isinstance(d, (int, float)):
                out.append(float(d))
    return out


def _hold_ratios(samples: list[SessionActionSample]) -> list[float]:
    out: list[float] = []
    for s in samples:
        if not s.actions:
            continue
        holds = sum(1 for _, a, _ in s.actions if a == "hold")
        out.append(holds / len(s.actions))
    return out


def pick_primary_template(samples: list[SessionActionSample]) -> TemplateId:
    dists = _buy_ma_distances(samples)
    if not dists:
        return "ma_breakout"
    med = median(dists)
    if med > 0.015:
        return "ma_breakout"
    if med < -0.01:
        return "pullback_ma"
    holds = _hold_ratios(samples)
    if holds and median(holds) < 0.35:
        return "ma_breakout"
    return "trend_hold"


def _fit_score(template_id: TemplateId, samples: list[SessionActionSample]) -> float:
    dists = _buy_ma_distances(samples)
    if not dists:
        return 0.55
    med = median(dists)
    if template_id == "ma_breakout":
        return min(0.95, 0.6 + max(0.0, med) * 8)
    if template_id == "pullback_ma":
        return min(0.92, 0.6 + max(0.0, -med) * 8)
    return 0.7


def generate_candidates_from_blind(
    *,
    samples: list[SessionActionSample],
    period: str,
    session_count: int,
    max_candidates: int = 3,
) -> list[StrategyCandidateDraft]:
    """生成 1–3 个候选 DSL（仅 blind 样本）。"""
    primary = pick_primary_template(samples)
    order: list[TemplateId] = [primary]
    for alt in ("ma_breakout", "pullback_ma", "trend_hold"):
        if alt not in order:
            order.append(alt)
    order = order[:max_candidates]

    param_sets: dict[TemplateId, list[tuple[int, int, int | None]]] = {
        "ma_breakout": [(20, 10, None), (20, 5, 25), (15, 8, None)],
        "pullback_ma": [(20, 10, 30), (25, 12, 25)],
        "trend_hold": [(20, 10, 40), (30, 15, 50)],
    }

    drafts: list[StrategyCandidateDraft] = []
    for i, tpl in enumerate(order):
        params_list = param_sets.get(tpl, [(20, 10, None)])
        entry_ma, exit_ma, max_hold = params_list[min(i, len(params_list) - 1)]
        fit = _fit_score(tpl, samples) - i * 0.05
        fit = max(0.4, min(0.98, fit))
        from iquant_strategy_dsl.templates import TEMPLATE_LABELS

        name = f"{TEMPLATE_LABELS[tpl]}·方案{i + 1}"
        dsl = build_template_dsl(
            template_id=tpl,
            name=name,
            period=period,
            fit_score=fit,
            blind_session_count=session_count,
            entry_ma=entry_ma,
            exit_ma=exit_ma,
            max_hold_days=max_hold,
        )
        validated = validate_dsl(dsl)
        rules = dsl_to_rule_lines(validated)
        rank = Decimal(str(round(fit - i * 0.03, 4)))
        drafts.append(
            StrategyCandidateDraft(
                template_id=tpl,
                name=name,
                dsl=validated,
                rules_summary=rules,
                rank_score=rank,
            )
        )
    return drafts
