"""批次模式总结规则引擎单测。"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from iquant_annotation_service.usecases.batch_profile import PairSample, build_batch_profile


def _pair(*, ret: str, days: int) -> PairSample:
    buy = datetime(2024, 1, 1, tzinfo=UTC)
    sell = buy + timedelta(days=days)
    return PairSample(
        pair_id=uuid4(),
        session_id=uuid4(),
        full_code="sz300001",
        buy_bar_time=buy,
        sell_bar_time=sell,
        return_pct=Decimal(ret),
    )


def test_build_batch_profile_empty_pairs() -> None:
    r = build_batch_profile(pairs=[], completed_count=2, skipped_count=18, total_count=20)
    assert r.stats["pair_count"] == 0
    assert "有效样本不足" in r.insights[1]
    assert len(r.correction_options) == 5


def test_build_batch_profile_short_term_style() -> None:
    pairs = [_pair(ret="0.05", days=3) for _ in range(4)]
    r = build_batch_profile(pairs=pairs, completed_count=4, skipped_count=0, total_count=4)
    assert "偏短线" in r.profile_draft
    assert r.stats["pair_count"] == 4
    assert len(r.insights) >= 2


def test_build_batch_profile_outlier_when_enough_pairs() -> None:
    pairs = [
        _pair(ret="0.02", days=5),
        _pair(ret="0.03", days=6),
        _pair(ret="0.50", days=40),
    ]
    r = build_batch_profile(pairs=pairs, completed_count=3, skipped_count=0, total_count=3)
    assert len(r.outlier_pairs) == 1
    assert r.outlier_pairs[0]["full_code"] == "sz300001"
