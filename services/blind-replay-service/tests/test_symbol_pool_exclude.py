"""``pick_random_full_code`` 排除已训练标的的单元测试。"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from iquant_blind_replay_service.usecases import symbol_pool
from iquant_domain.errors import ValidationError
from iquant_market_service.usecases.schemas import BarPoint, BrowserSymbolRow


def _sym(code: str) -> BrowserSymbolRow:
    market = code[:2]
    return BrowserSymbolRow(
        full_code=code,
        code=code[2:],
        market=market,
        name=f"N-{code}",
    )


def _bar(i: int) -> BarPoint:
    base = datetime(2025, 1, 2, tzinfo=UTC)
    return BarPoint(
        bar_time=base + timedelta(days=i),
        open=Decimal("10"),
        high=Decimal("11"),
        low=Decimal("9"),
        close=Decimal("10"),
        volume=1000,
        amount=Decimal("10000"),
    )


@pytest.mark.anyio
async def test_pick_random_full_code_skips_excluded(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = [_sym("sh600000"), _sym("sh600001"), _sym("sz000001")]

    async def _list(**_: Any) -> tuple[list[BrowserSymbolRow], int]:
        return pool, len(pool)

    async def _resolve(**_: Any) -> list[BarPoint]:
        return [_bar(i) for i in range(60)]

    monkeypatch.setattr(symbol_pool, "list_symbols", _list)
    monkeypatch.setattr(symbol_pool, "resolve_session_range", _resolve)

    chosen = await symbol_pool.pick_random_full_code(
        period="day",
        exclude={"sh600000", "sh600001"},
    )
    assert chosen == "sz000001"


@pytest.mark.anyio
async def test_pick_random_full_code_raises_when_all_excluded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pool = [_sym("sh600000"), _sym("sh600001")]

    async def _list(**_: Any) -> tuple[list[BrowserSymbolRow], int]:
        return pool, len(pool)

    monkeypatch.setattr(symbol_pool, "list_symbols", _list)

    with pytest.raises(ValidationError, match="已全部训练过"):
        await symbol_pool.pick_random_full_code(
            period="day",
            exclude={"sh600000", "sh600001"},
        )


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
