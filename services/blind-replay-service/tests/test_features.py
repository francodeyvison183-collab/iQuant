"""特征快照单测。"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from iquant_market_service.usecases.schemas import BarPoint

from iquant_blind_replay_service.usecases.features import build_features_snapshot


def test_build_features_snapshot_ma20() -> None:
    bars: list[BarPoint] = []
    for i in range(25):
        t = datetime(2025, 1, 1, tzinfo=UTC) + timedelta(days=i)
        bars.append(
            BarPoint(
                bar_time=t,
                open=Decimal("10"),
                high=Decimal("11"),
                low=Decimal("9"),
                close=Decimal(str(10 + i * 0.1)),
                volume=1000 + i,
                amount=Decimal("10000"),
            )
        )
    snap = build_features_snapshot(bars, cursor_idx=24)
    assert snap["ma20"] is not None
    assert snap["ma20_dist"] is not None
