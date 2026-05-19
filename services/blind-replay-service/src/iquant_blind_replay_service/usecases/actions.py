"""盲测操作提交用例。"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog

from iquant_domain.errors import NotFoundError, ValidationError

from ..config import get_blind_replay_settings
from ..db import pg_session
from ..models import BlindActionORM
from ..repositories import blind_session_repo as repo
from .bar_loader import load_session_bars, visible_bar_idx
from .blind_display import count_trade_actions
from .features import build_features_snapshot
from .schemas import BlindActionIn, BlindSessionDetailOut
from .sessions import _ACTIVE, _FINISHED, _detail_out
from .simulation import apply_fill_after_decision

log = structlog.get_logger(__name__)

_VALID_ACTIONS = frozenset({"buy", "sell", "hold"})
_VALID_PERIODS = frozenset({"5m", "30m", "day", "week", "month"})


async def submit_blind_action(
    *,
    admin_user_id: int,
    session_id: UUID,
    body: BlindActionIn,
) -> BlindSessionDetailOut:
    if body.user_action not in _VALID_ACTIONS:
        raise ValidationError("user_action 须为 buy、sell 或 hold")

    cfg = get_blind_replay_settings()

    async with pg_session() as s:
        row = await repo.get_session_for_admin(
            s, session_id=session_id, admin_user_id=admin_user_id
        )
        if row is None:
            raise NotFoundError("盲测会话不存在")
        if row.status != _ACTIVE:
            raise ValidationError("会话已结束，无法提交操作")

        action_period = (body.period or row.period).strip() or row.period
        if action_period not in _VALID_PERIODS:
            raise ValidationError(f"不支持的周期 {action_period}")

        bars = await load_session_bars(
            full_code=row.full_code,
            period=action_period,
            range_start=row.range_start,
            range_end=row.range_end,
        )
        idx = visible_bar_idx(bars, row.cursor_bar_time, row.cursor_period)
        if idx < 0:
            raise ValidationError("当前周期暂无可见 K 线，请切换至更小周期")
        if idx >= len(bars) - 1:
            raise ValidationError("当前周期已至区间末尾，请切换周期或跳过本只")

        current_bar = bars[idx]
        if await repo.has_action_at_bar(s, session_id=session_id, bar_time=current_bar.bar_time):
            raise ValidationError("当前 K 线已提交过操作")

        # 轮级累计：开放轮内此前所有 switched 会话 + 当前会话此前的买卖数
        open_rows = await repo.list_open_round_sessions(s, admin_user_id=admin_user_id)
        prior_round_trades = sum(
            count_trade_actions(r.actions) for r in open_rows if r.id != row.id
        )
        trades_before_session = count_trade_actions(row.actions)
        round_trades_before = prior_round_trades + trades_before_session
        if round_trades_before >= cfg.required_trade_actions:
            raise ValidationError("本轮买卖次数已满，会话将结束")

        feat = build_features_snapshot(bars, cursor_idx=idx)
        action_row = BlindActionORM(
            session_id=row.id,
            bar_time=current_bar.bar_time,
            period=action_period,
            user_action=body.user_action,
            features_snapshot=feat,
            strategy_signal=None,
            user_reasons=body.user_reasons,
            confidence=body.confidence,
        )
        s.add(action_row)

        next_bar = bars[idx + 1]
        apply_fill_after_decision(
            row,
            user_action=body.user_action,
            decision_bar=current_bar,
            fill_bar=next_bar,
        )
        row.cursor_bar_time = next_bar.bar_time
        row.cursor_period = action_period

        is_trade = body.user_action in ("buy", "sell")
        round_trades_after = round_trades_before + (1 if is_trade else 0)

        if round_trades_after >= cfg.required_trade_actions:
            # 第 10 次买卖落在本会话 → 整轮以本会话作为正向终止
            row.status = _FINISHED
            row.completed_at = datetime.now(tz=UTC)
        # 注意：到达区间末尾不再自动 abandoned。后续 submit 会因 ``at_last_bar``
        # 校验失败而抛出错误，用户应改为切换下一只继续推进本轮。

        await s.commit()
        await s.refresh(row, ["actions"])
        log.info(
            "blind_action_recorded",
            session_id=str(session_id),
            action=body.user_action,
            period=action_period,
            bar_time=str(action_row.bar_time),
            round_trade_count=round_trades_after,
        )
        return await _detail_out(row, view_period=action_period)
