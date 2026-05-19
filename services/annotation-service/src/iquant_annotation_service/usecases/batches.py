"""标注批次队列用例（迭代 1a）。"""
from __future__ import annotations

import secrets
from uuid import UUID

import structlog
from iquant_domain.errors import NotFoundError, ValidationError
from iquant_market_service.usecases.query_bars import list_symbols

from ..db import pg_session
from ..models import LabelBatchORM, LabelBatchSummaryORM, LabelQueueItemORM
from ..repositories import label_batch_repo as batch_repo
from ..repositories import label_session_repo as session_repo
from .batch_profile import CORRECTION_OPTION_IDS, PairSample, build_batch_profile
from .labels import _session_to_out, create_label_session
from .schemas import (
    LabelBatchCreateIn,
    LabelBatchCurrentOut,
    LabelBatchListItemOut,
    LabelBatchOut,
    LabelBatchProgressOut,
    LabelBatchSummaryOut,
    LabelBatchSummaryPatchIn,
    LabelQueueItemOut,
    LabelSessionCreateIn,
    LabelSessionOut,
)

log = structlog.get_logger(__name__)

_POOL_FETCH_LIMIT = 500
_ITEM_PENDING = "pending"
_ITEM_IN_PROGRESS = "in_progress"
_ITEM_COMPLETED = "completed"
_ITEM_SKIPPED = "skipped"


def _progress(batch: LabelBatchORM) -> LabelBatchProgressOut:
    items = batch.items
    total = len(items)
    completed = sum(1 for i in items if i.status == _ITEM_COMPLETED)
    skipped = sum(1 for i in items if i.status == _ITEM_SKIPPED)
    pending = sum(1 for i in items if i.status in (_ITEM_PENDING, _ITEM_IN_PROGRESS))
    current = next(
        (i for i in items if i.status in (_ITEM_PENDING, _ITEM_IN_PROGRESS)),
        None,
    )
    current_index = (current.sort_order + 1) if current is not None else None
    return LabelBatchProgressOut(
        total=total,
        completed=completed,
        skipped=skipped,
        pending=pending,
        current_index=current_index,
    )


async def _item_pair_count(s, item: LabelQueueItemORM) -> int:  # type: ignore[no-untyped-def]
    if item.session_id is None:
        return 0
    return await batch_repo.session_pair_count(s, session_id=item.session_id)


async def _item_to_out(s, item: LabelQueueItemORM) -> LabelQueueItemOut:  # type: ignore[no-untyped-def]
    return LabelQueueItemOut(
        id=item.id,
        sort_order=item.sort_order,
        full_code=item.full_code,
        symbol_name=item.symbol_name,
        status=item.status,
        skip_reason=item.skip_reason,
        session_id=item.session_id,
        pair_count=await _item_pair_count(s, item),
    )


async def _batch_to_out(s, batch: LabelBatchORM) -> LabelBatchOut:  # type: ignore[no-untyped-def]
    item_outs = [await _item_to_out(s, i) for i in sorted(batch.items, key=lambda x: x.sort_order)]
    return LabelBatchOut(
        id=batch.id,
        period=batch.period,
        market_filter=batch.market_filter,
        batch_size=batch.batch_size,
        status=batch.status,
        created_at=batch.created_at,
        completed_at=batch.completed_at,
        progress=_progress(batch),
        items=item_outs,
    )


async def _pick_random_symbols(
    *,
    market: str | None,
    count: int,
) -> list[tuple[str, str]]:
    items, _total = await list_symbols(
        market=market or None,
        limit=_POOL_FETCH_LIMIT,
        offset=0,
        scope="with_bars",
    )
    if len(items) < count:
        raise ValidationError(
            f"可用标的不足 {count} 只（当前 {len(items)}），请先在「数据更新」导入更多行情"
        )
    picked = secrets.SystemRandom().sample(items, count)
    return [(r.full_code, r.name or r.code) for r in picked]


def _find_active_item(batch: LabelBatchORM) -> LabelQueueItemORM | None:
    for item in sorted(batch.items, key=lambda x: x.sort_order):
        if item.status in (_ITEM_PENDING, _ITEM_IN_PROGRESS):
            return item
    return None


async def _ensure_item_session(
    s,  # type: ignore[no-untyped-def]
    *,
    admin_user_id: int,
    batch: LabelBatchORM,
    item: LabelQueueItemORM,
) -> LabelSessionOut:
    if item.session_id is not None:
        row = await session_repo.get_session_for_admin(
            s, session_id=item.session_id, admin_user_id=admin_user_id
        )
        if row is not None:
            return _session_to_out(row)

    idem = f"batch-{batch.id}-item-{item.id}"[:128]
    session = await create_label_session(
        admin_user_id=admin_user_id,
        body=LabelSessionCreateIn(
            full_code=item.full_code,
            period=batch.period,
            title=f"{item.symbol_name or item.full_code} · 理想买卖表达",
        ),
        idempotency_key=idem,
    )
    item.session_id = session.id
    await s.flush()
    return session


def _summary_to_out(row: LabelBatchSummaryORM) -> LabelBatchSummaryOut:
    return LabelBatchSummaryOut(
        batch_id=row.batch_id,
        stats=row.stats_json,
        profile_draft=row.profile_draft,
        insights=list(row.insights_json),
        correction_options=list(row.correction_options_json),
        user_corrections=list(row.user_corrections_json),
        outlier_pairs=list(row.stats_json.get("outlier_pairs", []))
        if isinstance(row.stats_json.get("outlier_pairs"), list)
        else [],
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _generate_batch_summary(s, batch: LabelBatchORM) -> LabelBatchSummaryORM:  # type: ignore[no-untyped-def]
    existing = await batch_repo.get_summary(s, batch_id=batch.id)
    if existing is not None:
        return existing

    raw_pairs = await batch_repo.load_pair_samples_for_batch(s, batch_id=batch.id)
    samples = [
        PairSample(
            pair_id=p.id,
            session_id=p.session_id,
            full_code=fc,
            buy_bar_time=p.buy_bar_time,
            sell_bar_time=p.sell_bar_time,
            return_pct=p.return_pct,
        )
        for p, fc in raw_pairs
    ]
    prog = _progress(batch)
    profile = build_batch_profile(
        pairs=samples,
        completed_count=prog.completed,
        skipped_count=prog.skipped,
        total_count=prog.total,
    )
    stats = dict(profile.stats)
    stats["outlier_pairs"] = profile.outlier_pairs
    return await batch_repo.upsert_summary(
        s,
        batch_id=batch.id,
        stats_json=stats,
        profile_draft=profile.profile_draft,
        insights_json=profile.insights,
        correction_options_json=profile.correction_options,
        user_corrections_json=[],
    )


async def _maybe_complete_batch(s, batch: LabelBatchORM) -> None:  # type: ignore[no-untyped-def]
    if _find_active_item(batch) is None and batch.status == "active":
        await batch_repo.mark_batch_completed(s, batch=batch)
        await _generate_batch_summary(s, batch=batch)


async def create_label_batch(
    *,
    admin_user_id: int,
    body: LabelBatchCreateIn,
    idempotency_key: str,
) -> LabelBatchOut:
    _ = idempotency_key
    symbols = await _pick_random_symbols(market=body.market, count=body.batch_size)
    batch_row = LabelBatchORM(
        admin_user_id=admin_user_id,
        period=body.period.strip() or "day",
        market_filter=body.market.strip() if body.market else None,
        batch_size=len(symbols),
        status="active",
    )
    async with pg_session() as s:
        s.add(batch_row)
        await s.flush()
        for idx, (fc, name) in enumerate(symbols):
            s.add(
                LabelQueueItemORM(
                    batch_id=batch_row.id,
                    sort_order=idx,
                    full_code=fc,
                    symbol_name=name,
                    status=_ITEM_PENDING,
                )
            )
        await s.commit()

    log.info("label_batch_created", batch_id=str(batch_row.id), size=len(symbols))
    return await get_label_batch(admin_user_id=admin_user_id, batch_id=batch_row.id)


async def get_label_batch(*, admin_user_id: int, batch_id: UUID) -> LabelBatchOut:
    async with pg_session() as s:
        batch = await batch_repo.get_batch_for_admin(
            s, batch_id=batch_id, admin_user_id=admin_user_id
        )
        if batch is None:
            raise NotFoundError("标注批次不存在")
        return await _batch_to_out(s, batch)


async def get_batch_current(
    *,
    admin_user_id: int,
    batch_id: UUID,
) -> LabelBatchCurrentOut:
    async with pg_session() as s:
        batch = await batch_repo.get_batch_for_admin(
            s, batch_id=batch_id, admin_user_id=admin_user_id
        )
        if batch is None:
            raise NotFoundError("标注批次不存在")

        item = _find_active_item(batch)
        if item is None:
            if batch.status == "active":
                await batch_repo.mark_batch_completed(s, batch=batch)
                await s.commit()
            batch_out = await _batch_to_out(s, batch)
            return LabelBatchCurrentOut(
                batch=batch_out,
                current_item=None,
                session=None,
                done=True,
            )

        if item.status == _ITEM_PENDING:
            item.status = _ITEM_IN_PROGRESS
        session_out = await _ensure_item_session(
            s, admin_user_id=admin_user_id, batch=batch, item=item
        )
        await s.commit()

        fresh = await batch_repo.get_batch_for_admin(
            s, batch_id=batch_id, admin_user_id=admin_user_id
        )
        assert fresh is not None
        item = _find_active_item(fresh)
        assert item is not None
        batch_out = await _batch_to_out(s, fresh)
        item_out = await _item_to_out(s, item)
        return LabelBatchCurrentOut(
            batch=batch_out,
            current_item=item_out,
            session=session_out,
            done=False,
        )


async def skip_queue_item(
    *,
    admin_user_id: int,
    batch_id: UUID,
    item_id: UUID,
    skip_reason: str | None = None,
) -> LabelBatchCurrentOut:
    async with pg_session() as s:
        batch = await batch_repo.get_batch_for_admin(
            s, batch_id=batch_id, admin_user_id=admin_user_id
        )
        if batch is None:
            raise NotFoundError("标注批次不存在")
        item = await batch_repo.get_queue_item(s, batch_id=batch_id, item_id=item_id)
        if item is None:
            raise NotFoundError("队列项不存在")
        if item.status in (_ITEM_COMPLETED, _ITEM_SKIPPED):
            raise ValidationError("该标的已处理完毕")

        item.status = _ITEM_SKIPPED
        item.skip_reason = (skip_reason or "").strip()[:64] or None
        await _maybe_complete_batch(s, batch)
        await s.commit()

    return await get_batch_current(admin_user_id=admin_user_id, batch_id=batch_id)


async def complete_queue_item(
    *,
    admin_user_id: int,
    batch_id: UUID,
    item_id: UUID,
) -> LabelBatchCurrentOut:
    async with pg_session() as s:
        batch = await batch_repo.get_batch_for_admin(
            s, batch_id=batch_id, admin_user_id=admin_user_id
        )
        if batch is None:
            raise NotFoundError("标注批次不存在")
        item = await batch_repo.get_queue_item(s, batch_id=batch_id, item_id=item_id)
        if item is None:
            raise NotFoundError("队列项不存在")
        if item.status in (_ITEM_COMPLETED, _ITEM_SKIPPED):
            raise ValidationError("该标的已处理完毕")

        if item.session_id is None:
            raise ValidationError("请先完成至少一对买卖标注")
        pair_n = await batch_repo.session_pair_count(s, session_id=item.session_id)
        if pair_n < 1:
            raise ValidationError("请先完成至少一对买卖标注")

        item.status = _ITEM_COMPLETED
        await _maybe_complete_batch(s, batch)
        await s.commit()

    return await get_batch_current(admin_user_id=admin_user_id, batch_id=batch_id)


async def get_batch_summary(*, admin_user_id: int, batch_id: UUID) -> LabelBatchSummaryOut:
    async with pg_session() as s:
        batch = await batch_repo.get_batch_for_admin(
            s, batch_id=batch_id, admin_user_id=admin_user_id
        )
        if batch is None:
            raise NotFoundError("标注批次不存在")
        row = await batch_repo.get_summary(s, batch_id=batch_id)
        if row is None:
            if batch.status != "completed":
                raise ValidationError("批次尚未完成，暂无总结")
            row = await _generate_batch_summary(s, batch)
            await s.commit()
        return _summary_to_out(row)


async def patch_batch_summary(
    *,
    admin_user_id: int,
    batch_id: UUID,
    body: LabelBatchSummaryPatchIn,
) -> LabelBatchSummaryOut:
    for cid in body.user_corrections:
        if cid not in CORRECTION_OPTION_IDS:
            raise ValidationError(f"无效的修正项：{cid}")

    async with pg_session() as s:
        batch = await batch_repo.get_batch_for_admin(
            s, batch_id=batch_id, admin_user_id=admin_user_id
        )
        if batch is None:
            raise NotFoundError("标注批次不存在")
        row = await batch_repo.get_summary(s, batch_id=batch_id)
        if row is None:
            row = await _generate_batch_summary(s, batch)
        row.user_corrections_json = list(body.user_corrections)
        await s.commit()
        await s.refresh(row)
        return _summary_to_out(row)


async def list_label_batches(
    *, admin_user_id: int, limit: int, offset: int
) -> tuple[list[LabelBatchListItemOut], int]:
    async with pg_session() as s:
        rows, total = await batch_repo.list_batches_for_admin(
            s, admin_user_id=admin_user_id, limit=limit, offset=offset
        )
        out: list[LabelBatchListItemOut] = []
        for batch in rows:
            prog = _progress(batch)
            summary = await batch_repo.get_summary(s, batch_id=batch.id)
            pair_count = await batch_repo.total_pairs_in_batch(s, batch_id=batch.id)
            out.append(
                LabelBatchListItemOut(
                    id=batch.id,
                    period=batch.period,
                    market_filter=batch.market_filter,
                    batch_size=batch.batch_size,
                    status=batch.status,
                    created_at=batch.created_at,
                    completed_at=batch.completed_at,
                    completed_count=prog.completed,
                    skipped_count=prog.skipped,
                    pair_count=pair_count,
                    profile_draft=summary.profile_draft if summary else None,
                )
            )
        return out, total
