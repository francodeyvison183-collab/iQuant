"""DSL 校验。"""
from __future__ import annotations

from iquant_domain.errors import ValidationError

from .models import SCHEMA_VERSION, BehaviorStrategyDSL


def validate_dsl(doc: dict[str, object] | BehaviorStrategyDSL) -> BehaviorStrategyDSL:
    """解析并校验 DSL；非法则抛 ValidationError。"""
    try:
        if isinstance(doc, BehaviorStrategyDSL):
            model = doc
        else:
            model = BehaviorStrategyDSL.model_validate(doc)
    except Exception as e:
        raise ValidationError(f"策略 DSL 无效: {e}") from e

    if model.schema_version != SCHEMA_VERSION:
        raise ValidationError(f"不支持的 DSL 版本: {model.schema_version}")

    if model.meta.source != "blind_replay":
        raise ValidationError("MVP 仅支持 source=blind_replay 的行为策略")

    if model.entry.type not in ("cross_above", "cross_below"):
        raise ValidationError("入场规则类型无效")

    if model.exit.type not in ("cross_above", "cross_below", "hold_days_max"):
        raise ValidationError("出场规则类型无效")

    return model
