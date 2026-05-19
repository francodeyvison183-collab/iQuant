"""盲测脱敏与买卖计数。"""
from __future__ import annotations

from types import SimpleNamespace

from iquant_blind_replay_service.usecases.blind_display import (
    count_trade_actions,
    display_code,
    display_name,
    is_revealed,
    mask_full_code,
    mask_symbol_name,
)


def test_count_trade_actions_excludes_hold() -> None:
    actions = [
        SimpleNamespace(user_action="buy"),
        SimpleNamespace(user_action="hold"),
        SimpleNamespace(user_action="sell"),
    ]
    assert count_trade_actions(actions) == 2  # type: ignore[arg-type]


def test_mask_full_code_keeps_prefix_and_suffix() -> None:
    assert mask_full_code("sh600000") == "sh****00"
    assert mask_full_code("sz000001") == "sz****01"


def test_mask_full_code_short_string() -> None:
    assert mask_full_code("abcd") == "a**d"


def test_mask_symbol_name_chinese() -> None:
    assert mask_symbol_name("招商银行") == "招**行"
    assert mask_symbol_name("贵州茅台") == "贵**台"


def test_mask_symbol_name_short() -> None:
    assert mask_symbol_name("中信") == "中*"


def test_display_reveals_finished_only() -> None:
    assert is_revealed("finished") is True
    assert is_revealed("active") is False
    assert is_revealed("abandoned") is False
    assert display_code(status="active", full_code="sh600000") == "sh****00"
    assert display_code(status="finished", full_code="sh600000") == "sh600000"
    assert display_name(status="active", name="招商银行") == "招**行"
    assert display_name(status="finished", name="招商银行") == "招商银行"
    assert display_name(status="active", name=None) is None
