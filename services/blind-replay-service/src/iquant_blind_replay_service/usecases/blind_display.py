"""盲测展示脱敏与买卖计数。"""
from __future__ import annotations

from collections.abc import Iterable

from ..models import BlindActionORM

_FINISHED_VISIBLE_STATUSES = frozenset({"finished"})


def count_trade_actions(actions: Iterable[BlindActionORM]) -> int:
    """买卖操作次数（buy/sell），不含观望 hold。"""
    return sum(1 for a in actions if a.user_action in ("buy", "sell"))


def _mask_middle(text: str, *, keep_head: int, keep_tail: int) -> str:
    """保留首尾，把中间字符替换为同等数量的 ``*``。"""
    n = len(text)
    if n == 0:
        return text
    if n == 1:
        return "*"
    if n == 2:
        return f"{text[0]}*"
    if n <= keep_head + keep_tail:
        return f"{text[0]}{'*' * (n - 2)}{text[-1]}"
    return f"{text[:keep_head]}{'*' * (n - keep_head - keep_tail)}{text[-keep_tail:]}"


def mask_full_code(code: str) -> str:
    """``sh600000`` → ``sh****00``；保留交易所前缀与末尾两位。"""
    return _mask_middle(code, keep_head=2, keep_tail=2)


def mask_symbol_name(name: str) -> str:
    """``招商银行`` → ``招**行``；保留首尾各 1 个字符。"""
    return _mask_middle(name, keep_head=1, keep_tail=1)


def is_revealed(status: str) -> bool:
    """已完成轮次的会话不脱敏。"""
    return status in _FINISHED_VISIBLE_STATUSES


def display_code(*, status: str, full_code: str) -> str:
    return full_code if is_revealed(status) else mask_full_code(full_code)


def display_name(*, status: str, name: str | None) -> str | None:
    if not name:
        return name
    return name if is_revealed(status) else mask_symbol_name(name)
