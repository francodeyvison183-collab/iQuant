"""从 blind 样本生成候选 DSL。"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from iquant_blind_replay_service.usecases.consistency_profile import SessionActionSample
from iquant_strategy_service.usecases.generate_from_blind import (
    generate_candidates_from_blind,
    pick_primary_template,
)


def _sample(bias: float) -> SessionActionSample:
    t = datetime(2025, 6, 1, tzinfo=UTC)
    return SessionActionSample(
        session_id=uuid4(),
        full_code="sz300750",
        actions=[
            (t, "hold", {"ma20_dist": 0.0}),
            (t, "buy", {"ma20_dist": bias}),
            (t, "sell", {"ma20_dist": 0.0}),
        ],
    )


def test_pick_breakout_template() -> None:
    samples = [_sample(0.03), _sample(0.025), _sample(0.02)]
    assert pick_primary_template(samples) == "ma_breakout"


def test_generate_only_blind_produces_dsl() -> None:
    samples = [_sample(0.02) for _ in range(3)]
    drafts = generate_candidates_from_blind(
        samples=samples, period="day", session_count=3, max_candidates=2
    )
    assert 1 <= len(drafts) <= 2
    assert drafts[0].dsl.meta.source == "blind_replay"
    assert len(drafts[0].rules_summary) >= 3
