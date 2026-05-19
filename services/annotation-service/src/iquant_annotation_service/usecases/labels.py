"""历史标注用例。"""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy.exc import IntegrityError

from iquant_domain.errors import NotFoundError, ValidationError

from ..db import pg_session
from ..models import LabelPairORM, LabelSessionORM
from ..repositories import label_session_repo as repo
from .pair_math import compute_pair_return_pct
from .schemas import LabelPairIn, LabelPairOut, LabelSessionCreateIn, LabelSessionOut, LabelSessionSummaryOut

log = structlog.get_logger(__name__)

_MAX_PAIRS = 500


def _validate_pairs(pairs: list[LabelPairIn]) -> list[LabelPairORM]:
    if len(pairs) > _MAX_PAIRS:
        raise ValidationError(f"单笔会话最多 {_MAX_PAIRS} 对标注")
    out: list[LabelPairORM] = []
    for i, p in enumerate(pairs):
        if p.sell_bar_time <= p.buy_bar_time:
            raise ValidationError(f"第 {i + 1} 对：卖出 K 线时间必须晚于买入")
        rp = compute_pair_return_pct(p.buy_close, p.sell_close)
        out.append(
            LabelPairORM(
                sort_order=i,
                buy_bar_time=p.buy_bar_time,
                sell_bar_time=p.sell_bar_time,
                buy_close=p.buy_close,
                sell_close=p.sell_close,
                return_pct=rp,
            )
        )
    return out


def _session_to_out(row: LabelSessionORM) -> LabelSessionOut:
    prs = sorted(row.pairs, key=lambda x: x.sort_order)
    return LabelSessionOut(
        id=row.id,
        full_code=row.full_code,
        period=row.period,
        title=row.title,
        created_at=row.created_at,
        updated_at=row.updated_at,
        pairs=[
            LabelPairOut(
                id=p.id,
                sort_order=p.sort_order,
                buy_bar_time=p.buy_bar_time,
                sell_bar_time=p.sell_bar_time,
                buy_close=str(p.buy_close),
                sell_close=str(p.sell_close),
                return_pct=str(p.return_pct),
            )
            for p in prs
        ],
    )


async def create_label_session(
    *,
    admin_user_id: int,
    body: LabelSessionCreateIn,
    idempotency_key: str,
) -> LabelSessionOut:
    async with pg_session() as s:
        existing = await repo.find_session_by_idempotency(
            s, admin_user_id=admin_user_id, idempotency_key=idempotency_key
        )
        if existing is not None:
            await s.refresh(existing, ["pairs"])
            log.info("label_session_idempotent_hit", session_id=str(existing.id))
            return _session_to_out(existing)

        row = LabelSessionORM(
            admin_user_id=admin_user_id,
            full_code=body.full_code.strip(),
            period=body.period.strip() or "day",
            title=body.title.strip() if body.title else None,
            idempotency_key=idempotency_key,
        )
        s.add(row)
        try:
            await s.flush()
            sid = row.id
            await s.commit()
        except IntegrityError:
            await s.rollback()
            async with pg_session() as s2:
                hit = await repo.find_session_by_idempotency(
                    s2, admin_user_id=admin_user_id, idempotency_key=idempotency_key
                )
                if hit is None:
                    raise
                await s2.refresh(hit, ["pairs"])
                return _session_to_out(hit)

    async with pg_session() as s3:
        fresh = await repo.get_session_for_admin(
            s3, session_id=sid, admin_user_id=admin_user_id
        )
        assert fresh is not None
        return _session_to_out(fresh)


async def list_label_sessions(
    *, admin_user_id: int, limit: int, offset: int
) -> tuple[list[LabelSessionSummaryOut], int]:
    async with pg_session() as s:
        rows, total = await repo.list_sessions_for_admin(
            s, admin_user_id=admin_user_id, limit=limit, offset=offset
        )
    summaries = [
        LabelSessionSummaryOut(
            id=r.id,
            full_code=r.full_code,
            period=r.period,
            title=r.title,
            created_at=r.created_at,
            pair_count=len(r.pairs),
        )
        for r in rows
    ]
    return summaries, total


async def get_label_session(*, admin_user_id: int, session_id: UUID) -> LabelSessionOut:
    async with pg_session() as s:
        row = await repo.get_session_for_admin(s, session_id=session_id, admin_user_id=admin_user_id)
    if row is None:
        raise NotFoundError("标注会话不存在")
    return _session_to_out(row)


async def delete_label_session(*, admin_user_id: int, session_id: UUID) -> None:
    async with pg_session() as s:
        row = await repo.get_session_for_admin(s, session_id=session_id, admin_user_id=admin_user_id)
        if row is None:
            raise NotFoundError("标注会话不存在")
        await repo.delete_session(s, row=row)
        await s.commit()


async def replace_label_pairs(
    *,
    admin_user_id: int,
    session_id: UUID,
    pairs: list[LabelPairIn],
    idempotency_key: str,
) -> LabelSessionOut:
    _ = idempotency_key
    orm_pairs = _validate_pairs(pairs)
    async with pg_session() as s:
        row = await repo.get_session_for_admin(s, session_id=session_id, admin_user_id=admin_user_id)
        if row is None:
            raise NotFoundError("标注会话不存在")
        await repo.delete_pairs_for_session(s, session_id=session_id)
        await repo.insert_pairs(s, session_id=session_id, pairs=orm_pairs)
        await s.commit()
    async with pg_session() as s2:
        fresh = await repo.get_session_for_admin(
            s2, session_id=session_id, admin_user_id=admin_user_id
        )
        assert fresh is not None
        return _session_to_out(fresh)
