"""``run_tdx_batch`` / ``AdaptiveConcurrency`` 行为烟测。"""
from __future__ import annotations

import asyncio

import pytest

from iquant_market_data.tdx.batch_runner import ADAPTIVE_GROW_SUCC, run_tdx_batch


@pytest.mark.asyncio
async def test_run_tdx_batch_counts_success_and_failure() -> None:
    items = list(range(10))

    async def process_one(i: int) -> bool:
        await asyncio.sleep(0)
        return i % 2 == 0

    runtime: dict = {}
    stats = await run_tdx_batch(
        items, process_one, name="ut", log_summary=False, runtime_stats=runtime
    )
    assert stats["total"] == 10
    assert stats["success"] == 5
    assert stats["failed"] == 5
    assert runtime.get("elapsed_seconds", 0) >= 0
    assert "gate" in runtime
    assert runtime["gate"]["cap"] >= 2


@pytest.mark.asyncio
async def test_adaptive_grow_cap() -> None:
    from iquant_market_data.tdx.batch_runner import AdaptiveConcurrency

    gate = AdaptiveConcurrency(initial=2, minimum=2, maximum=4)
    for _ in range(ADAPTIVE_GROW_SUCC):
        await gate.on_success("ut")
    assert gate.cap == 3
