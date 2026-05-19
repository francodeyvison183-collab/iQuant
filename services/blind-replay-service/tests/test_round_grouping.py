"""轮次分组 / 累计 / 状态推导的纯函数单元测试。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import cast

from iquant_blind_replay_service.models import BlindSessionORM
from iquant_blind_replay_service.usecases.sessions import (
    group_sessions_into_rounds,
    round_status,
    round_trade_count,
)


@dataclass
class _Action:
    user_action: str


@dataclass
class _Session:
    status: str
    created_at: datetime
    actions: list[_Action] = field(default_factory=list)
    id: str = ""


def _mk(status: str, ts_offset_min: int, *, trades: int = 0, holds: int = 0) -> _Session:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    acts = [_Action("buy")] * trades + [_Action("hold")] * holds
    return _Session(
        status=status,
        created_at=base + timedelta(minutes=ts_offset_min),
        actions=acts,
        id=f"{status}-{ts_offset_min}",
    )


def _cast(rows: list[_Session]) -> list[BlindSessionORM]:
    return cast(list[BlindSessionORM], rows)


def test_group_single_finished_round() -> None:
    rows = _cast([
        _mk("switched", 0, trades=3),
        _mk("switched", 10, trades=4),
        _mk("finished", 20, trades=3),
    ])
    rounds = group_sessions_into_rounds(rows)
    assert len(rounds) == 1
    assert round_trade_count(rounds[0]) == 10
    assert round_status(rounds[0]) == "finished"


def test_group_open_round_in_progress() -> None:
    rows = _cast([
        _mk("switched", 0, trades=2),
        _mk("active", 10, trades=1),
    ])
    rounds = group_sessions_into_rounds(rows)
    assert len(rounds) == 1
    assert round_trade_count(rounds[0]) == 3
    assert round_status(rounds[0]) == "active"


def test_group_multiple_rounds_history() -> None:
    rows = _cast([
        _mk("switched", 0, trades=4),
        _mk("finished", 10, trades=6),
        _mk("switched", 20, trades=2),
        _mk("abandoned", 30, trades=1),
        _mk("active", 40, trades=0),
    ])
    rounds = group_sessions_into_rounds(rows)
    assert [round_status(g) for g in rounds] == ["finished", "abandoned", "active"]
    assert [round_trade_count(g) for g in rounds] == [10, 3, 0]


def test_holds_not_counted() -> None:
    rows = _cast([_mk("active", 0, trades=2, holds=5)])
    rounds = group_sessions_into_rounds(rows)
    assert round_trade_count(rounds[0]) == 2
