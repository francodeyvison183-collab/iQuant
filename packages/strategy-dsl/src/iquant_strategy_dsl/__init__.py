"""策略 DSL：schema、校验、模板。"""
from .models import BehaviorStrategyDSL, TemplateId
from .rules_text import dsl_to_rule_lines
from .templates import TEMPLATE_LABELS, build_template_dsl
from .validator import validate_dsl

__all__ = [
    "BehaviorStrategyDSL",
    "TemplateId",
    "TEMPLATE_LABELS",
    "build_template_dsl",
    "dsl_to_rule_lines",
    "validate_dsl",
]
