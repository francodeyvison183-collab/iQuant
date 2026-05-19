"""盲测随机标的抽取。"""
from __future__ import annotations

import secrets
from collections.abc import Iterable
from datetime import datetime

from iquant_domain.errors import ValidationError
from iquant_market_service.usecases.query_bars import list_symbols

from ..config import get_blind_replay_settings
from .bar_loader import resolve_session_range

_POOL_FETCH_LIMIT = 500
_MAX_TRIES = 48


async def pick_random_full_code(
    *,
    period: str,
    months_back: int | None = None,
    range_start: datetime | None = None,
    range_end: datetime | None = None,
    exclude: Iterable[str] | None = None,
) -> str:
    """从有 K 线数据的池中随机抽取一只满足区间长度要求的标的。

    ``exclude`` 中列出的代码会被跳过（用于「同区间同标的不重复训练」）。
    """
    items, _total = await list_symbols(
        market=None,
        limit=_POOL_FETCH_LIMIT,
        offset=0,
        scope="with_bars",
    )
    if not items:
        raise ValidationError("暂无可用行情标的，请先在「数据更新」导入 K 线")

    cfg = get_blind_replay_settings()
    excluded = {c.strip() for c in (exclude or ())}
    rng = secrets.SystemRandom()
    candidates = [s for s in items if s.full_code.strip() not in excluded]
    if not candidates:
        raise ValidationError(
            "该训练区间内的可用标的已全部训练过，请调整起止日期或继续训练已有会话"
        )
    rng.shuffle(candidates)
    last_err = "近端 K 线长度不足"

    for sym in candidates[:_MAX_TRIES]:
        code = sym.full_code.strip()
        try:
            bars = await resolve_session_range(
                full_code=code,
                period=period,
                months_back=months_back,
                range_start=range_start,
                range_end=range_end,
            )
        except ValueError as e:
            last_err = str(e)
            continue
        if len(bars) >= cfg.min_bars_in_range:
            return code

    raise ValidationError(
        f"未能随机抽到满足训练条件的标的（需至少 {cfg.min_bars_in_range} 根 K 线）。{last_err}"
    )
