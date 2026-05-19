"""盲测会话用例。"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import structlog
from iquant_domain.errors import NotFoundError, ValidationError
from iquant_market_service.usecases.query_bars import get_symbol_names
from sqlalchemy.exc import IntegrityError

from ..config import get_blind_replay_settings
from ..db import pg_session
from ..models import BlindActionORM, BlindSessionORM
from ..repositories import blind_session_repo as repo
from .bar_loader import (
    bar_point_to_out,
    load_session_bars,
    resolve_session_range,
    slice_visible_bars,
    visible_bar_idx,
)
from .blind_display import (
    count_trade_actions,
    display_code,
    display_name,
)
from .schemas import (
    BarPointOut,
    BlindActionOut,
    BlindRoundOut,
    BlindRoundStockOut,
    BlindSessionCreateIn,
    BlindSessionDetailOut,
    BlindSessionOut,
    BlindSessionSummaryOut,
)
from .symbol_pool import pick_random_full_code

log = structlog.get_logger(__name__)

_ACTIVE = "active"
_SWITCHED = "switched"
_FINISHED = "finished"
_ABANDONED = "abandoned"
_TERMINAL_STATUSES = frozenset({_FINISHED, _ABANDONED})
_OPEN_STATUSES = frozenset({_ACTIVE, _SWITCHED})


def group_sessions_into_rounds(
    rows: list[BlindSessionORM],
) -> list[list[BlindSessionORM]]:
    """按状态序列把会话切分成训练轮次。

    规则：按 ``created_at`` 升序遍历，遇到状态 ∈ ``{finished, abandoned}`` 的会话
    作为本轮终止；其余 ``active`` / ``switched`` 累计入下一轮。最后若仍有未终止的
    会话，作为"进行中"的开放轮一并返回。
    """
    rounds: list[list[BlindSessionORM]] = []
    cur: list[BlindSessionORM] = []
    for r in sorted(rows, key=lambda x: x.created_at):
        cur.append(r)
        if r.status in _TERMINAL_STATUSES:
            rounds.append(cur)
            cur = []
    if cur:
        rounds.append(cur)
    return rounds


def round_status(round_rows: list[BlindSessionORM]) -> str:
    last = round_rows[-1]
    if last.status in _TERMINAL_STATUSES:
        return last.status
    return _ACTIVE


def round_trade_count(round_rows: list[BlindSessionORM]) -> int:
    return sum(count_trade_actions(r.actions) for r in round_rows)


def _action_to_out(row: BlindActionORM) -> BlindActionOut:
    reasons = row.user_reasons
    return BlindActionOut(
        id=row.id,
        bar_time=row.bar_time,
        period=row.period,
        user_action=row.user_action,
        features_snapshot=dict(row.features_snapshot),
        strategy_signal=row.strategy_signal,
        user_reasons=list(reasons) if isinstance(reasons, list) else None,
        confidence=row.confidence,
        created_at=row.created_at,
    )


def _session_base(
    row: BlindSessionORM,
    *,
    symbol_name: str | None,
    round_trades: int,
) -> BlindSessionOut:
    cfg = get_blind_replay_settings()
    trades = count_trade_actions(row.actions)
    return BlindSessionOut(
        id=row.id,
        display_label=display_code(status=row.status, full_code=row.full_code),
        display_name=display_name(status=row.status, name=symbol_name),
        full_code=row.full_code,
        symbol_name=symbol_name,
        period=row.period,
        range_start=row.range_start,
        range_end=row.range_end,
        cursor_bar_time=row.cursor_bar_time,
        status=row.status,
        source=row.source,
        cash_balance=str(row.cash_balance),
        position_qty=str(row.position_qty),
        action_count=len(row.actions),
        trade_action_count=trades,
        round_trade_count=round_trades,
        required_trade_actions=cfg.required_trade_actions,
        created_at=row.created_at,
        updated_at=row.updated_at,
        completed_at=row.completed_at,
    )


async def _compute_round_trades(row: BlindSessionORM) -> int:
    """开放轮（含 ``row`` 本身）的累计买卖次数。"""
    if row.status in _TERMINAL_STATUSES:
        # 该会话作为某轮终止点，其所在轮的累计 = 该轮中所有 session 之和
        async with pg_session() as s:
            all_rows = await repo.list_all_sessions_for_admin(
                s, admin_user_id=row.admin_user_id
            )
        for rnd in group_sessions_into_rounds(all_rows):
            if any(r.id == row.id for r in rnd):
                return round_trade_count(rnd)
        return count_trade_actions(row.actions)
    async with pg_session() as s:
        open_rows = await repo.list_open_round_sessions(
            s, admin_user_id=row.admin_user_id
        )
    seen_self = any(r.id == row.id for r in open_rows)
    base_total = sum(count_trade_actions(r.actions) for r in open_rows)
    return base_total + (0 if seen_self else count_trade_actions(row.actions))


async def _detail_out(
    row: BlindSessionORM,
    *,
    view_period: str | None = None,
) -> BlindSessionDetailOut:
    cfg = get_blind_replay_settings()
    period = (view_period or row.period).strip() or row.period
    bars = await load_session_bars(
        full_code=row.full_code,
        period=period,
        range_start=row.range_start,
        range_end=row.range_end,
    )
    visible = slice_visible_bars(
        bars,
        cursor_bar_time=row.cursor_bar_time,
        cursor_period=row.cursor_period,
        max_visible=cfg.chart_visible_max_bars,
    )
    names = await get_symbol_names([row.full_code])
    round_trades = await _compute_round_trades(row)
    base = _session_base(row, symbol_name=names.get(row.full_code), round_trades=round_trades)
    idx = visible_bar_idx(bars, row.cursor_bar_time, row.cursor_period)
    can_act = (
        row.status == _ACTIVE
        and idx >= 0
        and idx < len(bars) - 1
        and round_trades < cfg.required_trade_actions
    )
    return BlindSessionDetailOut(
        **base.model_dump(),
        view_period=period,
        visible_bars=[BarPointOut.model_validate(bar_point_to_out(b)) for b in visible],
        actions=[_action_to_out(a) for a in sorted(row.actions, key=lambda x: x.bar_time)],
        can_act=can_act,
    )


def _resolve_requested_range(
    body: BlindSessionCreateIn,
) -> tuple[datetime, datetime]:
    """得到本次训练所对应的"区间唯一键"，用于跨会话去重。

    用户显式传入 ``range_start`` / ``range_end`` 时取之；否则按 ``months_back``
    回退到近 N 个月窗口（此时不同时刻发起的训练会得到不同的 end，天然不去重）。
    """
    if body.range_start is not None and body.range_end is not None:
        return body.range_start, body.range_end
    cfg = get_blind_replay_settings()
    months = body.months_back if body.months_back is not None else cfg.default_months_back
    end = datetime.now(tz=UTC)
    start = end - timedelta(days=months * 31)
    return start, end


async def create_blind_session(
    *,
    admin_user_id: int,
    body: BlindSessionCreateIn,
    idempotency_key: str,
) -> BlindSessionDetailOut:
    cfg = get_blind_replay_settings()
    async with pg_session() as s:
        existing = await repo.find_session_by_idempotency(
            s, admin_user_id=admin_user_id, idempotency_key=idempotency_key
        )
        if existing is not None:
            await s.refresh(existing, ["actions"])
            return await _detail_out(existing)

    requested_start, requested_end = _resolve_requested_range(body)

    async with pg_session() as s_ex:
        excluded = await repo.list_used_full_codes_in_range(
            s_ex,
            admin_user_id=admin_user_id,
            range_start=requested_start,
            range_end=requested_end,
        )
        open_round = await repo.list_open_round_sessions(
            s_ex, admin_user_id=admin_user_id
        )
        # 当前开放轮内的标的也不能重复
        excluded = set(excluded) | {r.full_code for r in open_round}

    full_code = body.full_code.strip() if body.full_code else None
    if full_code is None:
        full_code = await pick_random_full_code(
            period=body.period,
            months_back=body.months_back,
            range_start=requested_start,
            range_end=requested_end,
            exclude=excluded,
        )
    elif full_code in excluded:
        raise ValidationError(
            "该标的在所选训练区间已训练过，请选择其他标的或调整起止日期"
        )

    try:
        bars = await resolve_session_range(
            full_code=full_code,
            period=body.period,
            months_back=body.months_back,
            range_start=requested_start,
            range_end=requested_end,
        )
    except ValueError as e:
        raise ValidationError(str(e)) from e

    session_period = body.period.strip() or "day"
    warmup = min(cfg.warmup_bars, len(bars) - 2)
    start_bar = bars[warmup]
    row = BlindSessionORM(
        admin_user_id=admin_user_id,
        full_code=full_code,
        period=session_period,
        range_start=requested_start,
        range_end=requested_end,
        cursor_bar_time=start_bar.bar_time,
        cursor_period=session_period,
        status=_ACTIVE,
        idempotency_key=idempotency_key,
        cash_balance=Decimal("1000000"),
        position_qty=Decimal("0"),
    )
    async with pg_session() as s:
        s.add(row)
        try:
            await s.commit()
        except IntegrityError:
            await s.rollback()
            async with pg_session() as s2:
                hit = await repo.find_session_by_idempotency(
                    s2, admin_user_id=admin_user_id, idempotency_key=idempotency_key
                )
                if hit is None:
                    raise
                await s2.refresh(hit, ["actions"])
                return await _detail_out(hit)

    log.info("blind_session_created", session_id=str(row.id))
    async with pg_session() as s3:
        fresh = await repo.get_session_for_admin(
            s3, session_id=row.id, admin_user_id=admin_user_id
        )
        assert fresh is not None
        return await _detail_out(fresh)


async def get_blind_session(
    *,
    admin_user_id: int,
    session_id: UUID,
    view_period: str | None = None,
) -> BlindSessionDetailOut:
    async with pg_session() as s:
        row = await repo.get_session_for_admin(
            s, session_id=session_id, admin_user_id=admin_user_id
        )
        if row is None:
            raise NotFoundError("盲测会话不存在")
        return await _detail_out(row, view_period=view_period)


async def list_blind_sessions(
    *,
    admin_user_id: int,
    limit: int,
    offset: int,
    status: str | None,
) -> tuple[list[BlindSessionSummaryOut], int]:
    async with pg_session() as s:
        rows, total = await repo.list_sessions_for_admin(
            s, admin_user_id=admin_user_id, limit=limit, offset=offset, status=status
        )
    codes = sorted({r.full_code for r in rows})
    names = await get_symbol_names(codes)
    out = [
        BlindSessionSummaryOut(
            id=r.id,
            display_label=display_code(status=r.status, full_code=r.full_code),
            display_name=display_name(status=r.status, name=names.get(r.full_code)),
            full_code=r.full_code,
            symbol_name=names.get(r.full_code),
            period=r.period,
            status=r.status,
            action_count=len(r.actions),
            trade_action_count=count_trade_actions(r.actions),
            created_at=r.created_at,
            completed_at=r.completed_at,
        )
        for r in rows
    ]
    return out, total


async def finish_blind_session(*, admin_user_id: int, session_id: UUID) -> BlindSessionDetailOut:
    """显式结束本轮——通常由 ``submit_blind_action`` 在累计 10 次时自动触发，

    保留该端点是为了兼容客户端可能的手动调用：只有"开放轮累计 ≥ 阈值"才允许。
    """
    cfg = get_blind_replay_settings()
    async with pg_session() as s:
        row = await repo.get_session_for_admin(
            s, session_id=session_id, admin_user_id=admin_user_id
        )
        if row is None:
            raise NotFoundError("盲测会话不存在")
        if row.status != _ACTIVE:
            raise ValidationError("仅进行中的会话可结束")
        open_rows = await repo.list_open_round_sessions(s, admin_user_id=admin_user_id)
        total = sum(count_trade_actions(r.actions) for r in open_rows)
        if any(r.id == row.id for r in open_rows) is False:
            total += count_trade_actions(row.actions)
        if total < cfg.required_trade_actions:
            raise ValidationError(
                f"本轮需完成 {cfg.required_trade_actions} 次买入或卖出，当前 {total} 次"
            )
        row.status = _FINISHED
        row.completed_at = datetime.now(tz=UTC)
        await s.commit()
        await s.refresh(row, ["actions"])
        return await _detail_out(row)


async def skip_blind_session(*, admin_user_id: int, session_id: UUID) -> BlindSessionDetailOut:
    """切换下一只 / 跳过本只：当前会话标为 ``switched``，开放轮继续累计。

    若用户想"放弃整轮"，应在前端调用 ``abandon_blind_session``（如有）或本端点
    标记完终止轮——当前 MVP 仅暴露 switch 语义。
    """
    async with pg_session() as s:
        row = await repo.get_session_for_admin(
            s, session_id=session_id, admin_user_id=admin_user_id
        )
        if row is None:
            raise NotFoundError("盲测会话不存在")
        if row.status != _ACTIVE:
            raise ValidationError("仅进行中的会话可切换")
        row.status = _SWITCHED
        row.completed_at = datetime.now(tz=UTC)
        await s.commit()
        await s.refresh(row, ["actions"])
        log.info("blind_session_switched", session_id=str(session_id))
        return await _detail_out(row)


def _round_id_for(rows: list[BlindSessionORM]) -> UUID:
    """轮次合成 ID：终止 session.id（已结束轮），或最新 session.id（开放轮）。"""
    return rows[-1].id


def _round_to_out(
    rows: list[BlindSessionORM], *, name_lookup: dict[str, str]
) -> BlindRoundOut:
    cfg = get_blind_replay_settings()
    status = round_status(rows)
    stocks = [
        BlindRoundStockOut(
            session_id=r.id,
            display_label=display_code(status=r.status, full_code=r.full_code),
            display_name=display_name(status=r.status, name=name_lookup.get(r.full_code)),
            full_code=r.full_code,
            symbol_name=name_lookup.get(r.full_code),
            status=r.status,
            trade_action_count=count_trade_actions(r.actions),
            created_at=r.created_at,
        )
        for r in rows
    ]
    last = rows[-1]
    return BlindRoundOut(
        round_id=_round_id_for(rows),
        status=status,
        period=last.period,
        range_start=last.range_start,
        range_end=last.range_end,
        trade_action_count=round_trade_count(rows),
        required_trade_actions=cfg.required_trade_actions,
        stock_count=len(rows),
        started_at=rows[0].created_at,
        completed_at=last.completed_at if status in _TERMINAL_STATUSES else None,
        stocks=stocks,
    )


async def list_blind_rounds(
    *, admin_user_id: int, limit: int = 30
) -> list[BlindRoundOut]:
    """按训练轮次返回历史（最新轮在前）。"""
    async with pg_session() as s:
        rows = await repo.list_all_sessions_for_admin(s, admin_user_id=admin_user_id)
    if not rows:
        return []
    groups = group_sessions_into_rounds(rows)
    codes = sorted({r.full_code for grp in groups for r in grp})
    names = await get_symbol_names(codes)
    rounds_desc = list(reversed(groups))[:limit]
    return [_round_to_out(g, name_lookup=names) for g in rounds_desc]
