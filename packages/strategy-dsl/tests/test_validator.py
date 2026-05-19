"""DSL 校验单测。"""
from __future__ import annotations

import pytest
from iquant_domain.errors import ValidationError
from iquant_strategy_dsl import build_template_dsl, validate_dsl


def test_validate_template_dsl_ok() -> None:
    dsl = build_template_dsl(
        template_id="ma_breakout",
        name="测试",
        period="day",
        fit_score=0.8,
        blind_session_count=3,
    )
    out = validate_dsl(dsl)
    assert out.meta.template_id == "ma_breakout"


def test_validate_rejects_bad_version() -> None:
    dsl = build_template_dsl(
        template_id="ma_breakout",
        name="测试",
        period="day",
        fit_score=0.8,
        blind_session_count=3,
    )
    doc = dsl.model_dump(mode="json")
    doc["schema_version"] = "99"
    with pytest.raises(ValidationError):
        validate_dsl(doc)
