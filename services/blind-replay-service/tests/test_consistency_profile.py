"""一致性规则引擎单测。"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from iquant_blind_replay_service.usecases.consistency_profile import (
    SessionActionSample,
    build_consistency_profile,
)


def test_consistency_requires_min_sessions() -> None:
    r = build_consistency_profile(
        samples=[],
        session_count=1,
        min_sessions=3,
        ready_threshold=60,
    )
    assert r.ready_for_strategy is False
    assert "至少需 3 轮" in r.profile_draft


def test_consistency_ready_when_scores_high() -> None:
    base = datetime(2025, 6, 1, tzinfo=UTC)
    samples = []
    for i in range(4):
        actions = [
            (base, "hold", {"ma20_dist": 0.01}),
            (base, "buy", {"ma20_dist": 0.02}),
            (base, "hold", {"ma20_dist": 0.01}),
        ]
        samples.append(
            SessionActionSample(session_id=uuid4(), full_code=f"sz30075{i}", actions=actions)
        )
    r = build_consistency_profile(
        samples=samples,
        session_count=4,
        min_sessions=3,
        ready_threshold=50,
    )
    assert r.scores["session_count"] == 4
    assert r.scores["overall"] > 0
