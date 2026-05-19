"""历史 K 线标注 REST（迭代 1）。

路径前缀 ``/api/v1/labels/*``，与小程序共用契约；当前仅管理员 JWT 可读写本人会话。
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, Field

from iquant_annotation_service.usecases import batches as batch_uc
from iquant_annotation_service.usecases import labels as label_uc
from iquant_annotation_service.usecases.schemas import (
    LabelBatchCreateIn,
    LabelBatchSummaryPatchIn,
    LabelPairIn,
    LabelSessionCreateIn,
)
from iquant_domain.errors import ValidationError
from iquant_identity_service.usecases.schemas import AdminProfile

from ...deps import require_admin

router = APIRouter(prefix="/labels", tags=["labels"])
protected = APIRouter(dependencies=[Depends(require_admin)])


def _idem(x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key")) -> str:
    if not x_idempotency_key or len(x_idempotency_key.strip()) < 8:
        raise ValidationError("请求头 X-Idempotency-Key 必填且至少 8 字符")
    return x_idempotency_key.strip()[:128]


class ReplacePairsBody(BaseModel):
    pairs: list[LabelPairIn] = Field(default_factory=list)


class SkipItemBody(BaseModel):
    skip_reason: str | None = Field(default=None, max_length=64)


@protected.get("/batches")
async def api_list_label_batches(
    admin: AdminProfile = Depends(require_admin),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    rows, total = await batch_uc.list_label_batches(
        admin_user_id=admin.id, limit=limit, offset=offset
    )
    return {
        "code": 0,
        "data": [r.model_dump(mode="json") for r in rows],
        "total": total,
    }


@protected.post("/batches")
async def api_create_label_batch(
    body: LabelBatchCreateIn,
    admin: AdminProfile = Depends(require_admin),
    idempotency_key: str = Depends(_idem),
) -> dict:
    out = await batch_uc.create_label_batch(
        admin_user_id=admin.id,
        body=body,
        idempotency_key=idempotency_key,
    )
    return {"code": 0, "data": out.model_dump(mode="json")}


@protected.get("/batches/{batch_id}")
async def api_get_label_batch(
    batch_id: UUID,
    admin: AdminProfile = Depends(require_admin),
) -> dict:
    out = await batch_uc.get_label_batch(admin_user_id=admin.id, batch_id=batch_id)
    return {"code": 0, "data": out.model_dump(mode="json")}


@protected.get("/batches/{batch_id}/summary")
async def api_get_batch_summary(
    batch_id: UUID,
    admin: AdminProfile = Depends(require_admin),
) -> dict:
    out = await batch_uc.get_batch_summary(admin_user_id=admin.id, batch_id=batch_id)
    return {"code": 0, "data": out.model_dump(mode="json")}


@protected.patch("/batches/{batch_id}/summary")
async def api_patch_batch_summary(
    batch_id: UUID,
    body: LabelBatchSummaryPatchIn,
    admin: AdminProfile = Depends(require_admin),
) -> dict:
    out = await batch_uc.patch_batch_summary(
        admin_user_id=admin.id, batch_id=batch_id, body=body
    )
    return {"code": 0, "data": out.model_dump(mode="json")}


@protected.get("/batches/{batch_id}/current")
async def api_get_batch_current(
    batch_id: UUID,
    admin: AdminProfile = Depends(require_admin),
) -> dict:
    out = await batch_uc.get_batch_current(admin_user_id=admin.id, batch_id=batch_id)
    return {"code": 0, "data": out.model_dump(mode="json")}


@protected.post("/batches/{batch_id}/items/{item_id}/skip")
async def api_skip_batch_item(
    batch_id: UUID,
    item_id: UUID,
    body: SkipItemBody,
    admin: AdminProfile = Depends(require_admin),
) -> dict:
    out = await batch_uc.skip_queue_item(
        admin_user_id=admin.id,
        batch_id=batch_id,
        item_id=item_id,
        skip_reason=body.skip_reason,
    )
    return {"code": 0, "data": out.model_dump(mode="json")}


@protected.post("/batches/{batch_id}/items/{item_id}/complete")
async def api_complete_batch_item(
    batch_id: UUID,
    item_id: UUID,
    admin: AdminProfile = Depends(require_admin),
) -> dict:
    out = await batch_uc.complete_queue_item(
        admin_user_id=admin.id,
        batch_id=batch_id,
        item_id=item_id,
    )
    return {"code": 0, "data": out.model_dump(mode="json")}


@protected.post("/sessions")
async def api_create_label_session(
    body: LabelSessionCreateIn,
    admin: AdminProfile = Depends(require_admin),
    idempotency_key: str = Depends(_idem),
) -> dict:
    out = await label_uc.create_label_session(
        admin_user_id=admin.id,
        body=body,
        idempotency_key=idempotency_key,
    )
    return {"code": 0, "data": out.model_dump(mode="json")}


@protected.get("/sessions")
async def api_list_label_sessions(
    admin: AdminProfile = Depends(require_admin),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    rows, total = await label_uc.list_label_sessions(admin_user_id=admin.id, limit=limit, offset=offset)
    return {
        "code": 0,
        "data": [r.model_dump(mode="json") for r in rows],
        "total": total,
    }


@protected.get("/sessions/{session_id}")
async def api_get_label_session(
    session_id: UUID,
    admin: AdminProfile = Depends(require_admin),
) -> dict:
    out = await label_uc.get_label_session(admin_user_id=admin.id, session_id=session_id)
    return {"code": 0, "data": out.model_dump(mode="json")}


@protected.delete("/sessions/{session_id}")
async def api_delete_label_session(
    session_id: UUID,
    admin: AdminProfile = Depends(require_admin),
    idempotency_key: str = Depends(_idem),
) -> dict:
    _ = idempotency_key
    await label_uc.delete_label_session(admin_user_id=admin.id, session_id=session_id)
    return {"code": 0, "data": None}


@protected.put("/sessions/{session_id}/pairs")
async def api_replace_label_pairs(
    session_id: UUID,
    body: ReplacePairsBody,
    admin: AdminProfile = Depends(require_admin),
    idempotency_key: str = Depends(_idem),
) -> dict:
    out = await label_uc.replace_label_pairs(
        admin_user_id=admin.id,
        session_id=session_id,
        pairs=body.pairs,
        idempotency_key=idempotency_key,
    )
    return {"code": 0, "data": out.model_dump(mode="json")}


router.include_router(protected)
