"""在线批量任务运行时指标计算单测。"""
from __future__ import annotations

import time as time_mod

from iquant_market_service.usecases.batch_online_fetch import build_runtime_progress_fields


def test_build_runtime_progress_eta_and_concurrency() -> None:
    started = time_mod.monotonic() - 100.0
    fields = build_runtime_progress_fields(
        started_at=started,
        done=50,
        total=100,
        runtime_stats={
            "gate": {"cap": 4, "active": 3},
            "pool_cooldown_remain_seconds": 12.5,
            "batch_cooldown_until": 0.0,
        },
        concurrency_max=8,
        concurrency_initial=4,
    )
    assert fields["elapsed_seconds"] >= 99.0
    assert fields["eta_seconds"] is not None
    assert fields["eta_seconds"] > 0
    assert fields["speed_per_minute"] > 0
    assert fields["concurrency_cap"] == 4
    assert fields["concurrency_active"] == 3
    assert fields["concurrency_max"] == 8
    assert fields["pool_cooldown_remain_seconds"] == 12.5


def test_build_runtime_progress_no_eta_when_not_started() -> None:
    fields = build_runtime_progress_fields(
        started_at=time_mod.monotonic(),
        done=0,
        total=100,
        runtime_stats=None,
        concurrency_max=8,
        concurrency_initial=4,
    )
    assert fields["eta_seconds"] is None
    assert fields["speed_per_minute"] == 0.0
    assert fields["concurrency_cap"] == 4
