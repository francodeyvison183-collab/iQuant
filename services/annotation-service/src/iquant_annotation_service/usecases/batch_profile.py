"""批次标注节奏归纳（规则引擎，迭代 1b）。

产出为对用户标注样本的描述性摘要，供核对交易逻辑表达是否一致；
不构成买卖建议，也不替代下游 DSL 策略生成（策略翻译官链路中的中间反馈）。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from statistics import median
from uuid import UUID


@dataclass(frozen=True)
class PairSample:
    pair_id: UUID
    session_id: UUID
    full_code: str
    buy_bar_time: datetime
    sell_bar_time: datetime
    return_pct: Decimal


@dataclass(frozen=True)
class CorrectionOption:
    id: str
    label: str


CORRECTION_OPTION_IDS: frozenset[str] = frozenset(
    {
        "prefer_breakout",
        "prefer_pullback",
        "hold_longer",
        "take_profit_earlier",
        "mixed_style",
    }
)

CORRECTION_OPTIONS: tuple[CorrectionOption, ...] = (
    CorrectionOption(id="prefer_breakout", label="我的逻辑更偏突破追涨式入场"),
    CorrectionOption(id="prefer_pullback", label="我的逻辑更偏回调低吸式入场"),
    CorrectionOption(id="hold_longer", label="翻译成策略时，持有周期应更长"),
    CorrectionOption(id="take_profit_earlier", label="翻译成策略时，止盈应更早"),
    CorrectionOption(id="mixed_style", label="我的逻辑因标的/行情而异，难以用单一风格概括"),
)


def _hold_days(p: PairSample) -> float:
    delta = p.sell_bar_time - p.buy_bar_time
    return max(delta.total_seconds() / 86400.0, 0.0)


def _fmt_pct(v: Decimal) -> str:
    pct = float(v) * 100
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.2f}%"


@dataclass(frozen=True)
class BatchProfileResult:
    stats: dict[str, object]
    profile_draft: str
    insights: list[str]
    correction_options: list[dict[str, str]]
    outlier_pairs: list[dict[str, str]]


def build_batch_profile(
    *,
    pairs: list[PairSample],
    completed_count: int,
    skipped_count: int,
    total_count: int,
) -> BatchProfileResult:
    options = [{"id": o.id, "label": o.label} for o in CORRECTION_OPTIONS]
    if not pairs:
        return BatchProfileResult(
            stats={
                "pair_count": 0,
                "completed_symbols": completed_count,
                "skipped_symbols": skipped_count,
                "total_symbols": total_count,
            },
            profile_draft="本批未留下有效买卖对样本，建议再练一轮，以便积累可翻译为策略的标注样本。",
            insights=[
                f"本批完成 {completed_count} 只、跳过 {skipped_count} 只。",
                "有效样本不足，暂不推断持仓周期或止盈风格。",
            ],
            correction_options=options,
            outlier_pairs=[],
        )

    returns = [float(p.return_pct) for p in pairs]
    holds = [_hold_days(p) for p in pairs]
    wins = sum(1 for r in returns if r > 0)
    win_rate = wins / len(pairs)
    med_hold = median(holds)
    avg_ret = sum(returns) / len(returns)

    if med_hold < 5:
        hold_style = "偏短线"
        hold_hint = "持有周期较短"
    elif med_hold < 20:
        hold_style = "偏波段"
        hold_hint = "持有约两周左右的波段"
    else:
        hold_style = "偏中长线"
        hold_hint = "愿意持有更长时间"

    if avg_ret >= 0.05:
        ret_hint = "单笔区间收益偏乐观"
    elif avg_ret >= 0:
        ret_hint = "单笔区间收益略偏正"
    else:
        ret_hint = "单笔区间收益偏保守或止损较快"

    early_exits = sum(1 for r in returns if 0 < r < 0.03)
    early_ratio = early_exits / len(pairs)
    exit_hint = "止盈偏早" if early_ratio >= 0.5 else "止盈节奏相对均衡"

    profile = (
        f"你的标注样本显示：{hold_style}（中位持有约 {med_hold:.0f} 天），"
        f"胜率约 {win_rate * 100:.0f}%，{ret_hint}，{exit_hint}。"
    )

    insights = [
        f"共 {len(pairs)} 笔有效买卖对（完成 {completed_count} 只 / 跳过 {skipped_count} 只）。",
        f"区间收益中位数 {_fmt_pct(Decimal(str(median(returns))))}，平均 {_fmt_pct(Decimal(str(avg_ret)))}。",
        hold_hint + "。",
    ]
    if skipped_count / max(total_count, 1) >= 0.4:
        insights.append("跳过占比较高，可考虑缩小随机范围或专注熟悉板块。")

    outlier_pairs = _find_outliers(pairs, returns, holds)

    stats: dict[str, object] = {
        "pair_count": len(pairs),
        "completed_symbols": completed_count,
        "skipped_symbols": skipped_count,
        "total_symbols": total_count,
        "win_rate": f"{win_rate * 100:.1f}%",
        "median_hold_days": round(med_hold, 1),
        "median_return_pct": _fmt_pct(Decimal(str(median(returns)))),
        "avg_return_pct": _fmt_pct(Decimal(str(avg_ret))),
    }

    return BatchProfileResult(
        stats=stats,
        profile_draft=profile,
        insights=insights,
        correction_options=options,
        outlier_pairs=outlier_pairs,
    )


def _find_outliers(
    pairs: list[PairSample],
    returns: list[float],
    holds: list[float],
) -> list[dict[str, str]]:
    if len(pairs) < 3:
        return []
    med_r = median(returns)
    med_h = median(holds)
    scored: list[tuple[float, PairSample]] = []
    for p, r, h in zip(pairs, returns, holds, strict=True):
        score = abs(r - med_r) + abs(h - med_h) / max(med_h, 1.0) * 0.1
        scored.append((score, p))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[0][1]
    return [
        {
            "pair_id": str(top.pair_id),
            "session_id": str(top.session_id),
            "full_code": top.full_code,
            "return_pct": _fmt_pct(top.return_pct),
            "hold_days": str(int(_hold_days(top))),
        }
    ]
