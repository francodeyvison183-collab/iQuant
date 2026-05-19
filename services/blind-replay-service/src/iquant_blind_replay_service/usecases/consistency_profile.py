"""跨轮盲测一致性归纳（规则引擎，迭代 1b）。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import median, pstdev
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class SessionActionSample:
    session_id: UUID
    full_code: str
    actions: list[tuple[datetime, str, dict[str, Any]]]


@dataclass(frozen=True)
class CorrectionOption:
    id: str
    label: str


CORRECTION_OPTION_IDS: frozenset[str] = frozenset(
    {
        "entry_more_breakout",
        "entry_more_pullback",
        "hold_longer_blind",
        "exit_earlier_blind",
        "mixed_blind_style",
    }
)

CORRECTION_OPTIONS: tuple[CorrectionOption, ...] = (
    CorrectionOption(id="entry_more_breakout", label="盲测中我更常在突破上方区域买入"),
    CorrectionOption(id="entry_more_pullback", label="盲测中我更常在回调靠近均线时买入"),
    CorrectionOption(id="hold_longer_blind", label="多轮训练中持有周期偏长"),
    CorrectionOption(id="exit_earlier_blind", label="多轮训练中止盈偏早"),
    CorrectionOption(id="mixed_blind_style", label="不同标的/行情下风格差异大"),
)


@dataclass(frozen=True)
class ConsistencyProfileResult:
    scores: dict[str, Any]
    profile_draft: str
    insights: list[str]
    correction_options: list[dict[str, str]]
    ready_for_strategy: bool


def _hold_ratio(samples: list[SessionActionSample]) -> list[float]:
    out: list[float] = []
    for s in samples:
        if not s.actions:
            continue
        holds = sum(1 for _, a, _ in s.actions if a == "hold")
        out.append(holds / len(s.actions))
    return out


def _buy_ma_bias(samples: list[SessionActionSample]) -> list[float]:
    """买入时 ma20_dist 均值；无 ma 记 0。"""
    out: list[float] = []
    for s in samples:
        dists: list[float] = []
        for _, action, feat in s.actions:
            if action != "buy":
                continue
            d = feat.get("ma20_dist")
            if isinstance(d, (int, float)):
                dists.append(float(d))
        if dists:
            out.append(sum(dists) / len(dists))
    return out


def _score_from_spread(values: list[float], *, invert: bool = False) -> int:
    if len(values) < 2:
        return 70 if values else 0
    spread = pstdev(values) if len(values) > 1 else 0.0
    raw = max(0, 100 - int(spread * 400))
    return 100 - raw if invert else raw


def build_consistency_profile(
    *,
    samples: list[SessionActionSample],
    session_count: int,
    min_sessions: int,
    ready_threshold: int,
) -> ConsistencyProfileResult:
    options = [{"id": o.id, "label": o.label} for o in CORRECTION_OPTIONS]
    if session_count < min_sessions:
        return ConsistencyProfileResult(
            scores={
                "overall": 0,
                "entry_consistency": 0,
                "rhythm_consistency": 0,
                "session_count": session_count,
                "min_sessions_required": min_sessions,
            },
            profile_draft=(
                f"已完成 {session_count} 轮盲测，至少需 {min_sessions} 轮才能评估跨轮一致性。"
                "请继续训练后再查看报告。"
            ),
            insights=[
                f"当前完成轮次：{session_count} / {min_sessions}。",
                "报告为描述性归纳，不构成买卖建议。",
            ],
            correction_options=options,
            ready_for_strategy=False,
        )

    hold_rates = _hold_ratio(samples)
    buy_biases = _buy_ma_bias(samples)
    rhythm = _score_from_spread(hold_rates)
    entry = _score_from_spread(buy_biases) if buy_biases else 65
    overall = int((rhythm + entry) / 2)
    ready = overall >= ready_threshold and session_count >= min_sessions

    med_hold = median(hold_rates) if hold_rates else 0.0
    if med_hold >= 0.6:
        rhythm_hint = "观望占比偏高，节奏偏谨慎"
    elif med_hold <= 0.25:
        rhythm_hint = "交易频率偏高，节奏偏积极"
    else:
        rhythm_hint = "买卖与观望节奏相对均衡"

    profile = (
        f"基于 {session_count} 轮盲测：入场倾向一致性约 {entry} 分，"
        f"操作节奏一致性约 {rhythm} 分，综合 {overall} 分；{rhythm_hint}。"
    )
    if not ready:
        profile += " 建议再完成 1–2 轮同周期训练后再生成行为策略草案。"

    insights = [
        f"共纳入 {session_count} 轮已结束盲测会话。",
        f"综合一致性 {overall} 分（阈值 {ready_threshold}）。",
        "本摘要仅描述你在盲测中的行为模式，不构成买卖建议。",
    ]
    if buy_biases and len(buy_biases) >= 2:
        spread = pstdev(buy_biases)
        if spread > 0.03:
            insights.append("各轮买入时相对均线位置差异较大，可回看矛盾样本。")

    return ConsistencyProfileResult(
        scores={
            "overall": overall,
            "entry_consistency": entry,
            "rhythm_consistency": rhythm,
            "session_count": session_count,
            "median_hold_ratio": round(med_hold, 3),
        },
        profile_draft=profile,
        insights=insights,
        correction_options=options,
        ready_for_strategy=ready,
    )
