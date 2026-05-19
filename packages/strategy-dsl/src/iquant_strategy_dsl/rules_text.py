"""DSL → 人话规则列表（H5 展示）。"""
from __future__ import annotations

from .models import BehaviorStrategyDSL
from .templates import TEMPLATE_LABELS


def dsl_to_rule_lines(dsl: BehaviorStrategyDSL) -> list[str]:
    """生成自然语言规则摘要。"""
    tpl = TEMPLATE_LABELS.get(dsl.meta.template_id, dsl.meta.template_id)
    lines = [f"模板：{tpl}（{dsl.name}）", f"周期：{dsl.period}，仅做多。"]

    entry_ma = _ma_period(dsl.entry)
    exit_ma = _ma_period(dsl.exit)
    if dsl.entry.type == "cross_above" and entry_ma:
        lines.append(f"买入：收盘价上穿 MA{entry_ma}。")
    elif dsl.entry.type == "cross_above":
        lines.append("买入：满足模板定义的突破条件。")

    if dsl.exit.type == "cross_below" and exit_ma:
        lines.append(f"卖出：收盘价跌破 MA{exit_ma}。")
    elif dsl.exit.type == "hold_days_max" and dsl.exit.value is not None:
        lines.append(f"卖出：持仓超过 {int(dsl.exit.value)} 个交易日。")

    if dsl.risk.stop_loss_pct is not None:
        pct = float(dsl.risk.stop_loss_pct) * 100
        lines.append(f"风控：止损约 {pct:.1f}%。")
    if dsl.risk.max_hold_days is not None:
        lines.append(f"风控：最长持有 {dsl.risk.max_hold_days} 日。")

    lines.append(
        f"归纳自 {dsl.meta.blind_session_count} 轮盲测，拟合度 {dsl.meta.fit_score * 100:.0f}%（描述性，非荐股）。"
    )
    return lines


def _ma_period(clause) -> int | None:  # type: ignore[no-untyped-def]
    ref = clause.right or clause.left
    if ref and ref.indicator == "ma":
        p = ref.params.get("period")
        return int(p) if p is not None else None
    return None
