"""近端历史盲测 REST（迭代 1a/1b）。

路径前缀 ``/api/v1/replays/*``；可见 K 线由服务端按 ``cursor_bar_time`` 裁剪。
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, Field

from iquant_blind_replay_service.usecases import actions as action_uc
from iquant_blind_replay_service.usecases import consistency as consistency_uc
from iquant_blind_replay_service.usecases import sessions as session_uc
from iquant_blind_replay_service.usecases.schemas import (
    BlindActionIn,
    BlindConsistencyPatchIn,
    BlindSessionCreateIn,
)
from iquant_domain.errors import ValidationError
from iquant_identity_service.usecases.schemas import AdminProfile

from ...deps import require_admin

router = APIRouter(prefix="/replays", tags=["replays"])
protected = APIRouter(dependencies=[Depends(require_admin)])


def _idem(x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key")) -> str:
    if not x_idempotency_key or len(x_idempotency_key.strip()) < 8:
        raise ValidationError("请求头 X-Idempotency-Key 必填且至少 8 字符")
    return x_idempotency_key.strip()[:128]


class FinishBody(BaseModel):
    reason: str | None = Field(default=None, max_length=64)


@protected.post("/sessions")
async def api_create_blind_session(
    body: BlindSessionCreateIn,
    admin: AdminProfile = Depends(require_admin),
    idempotency_key: str = Depends(_idem),
) -> dict:
    out = await session_uc.create_blind_session(
        admin_user_id=admin.id,
        body=body,
        idempotency_key=idempotency_key,
    )
    return {"code": 0, "data": out.model_dump(mode="json")}


@protected.get("/sessions")
async def api_list_blind_sessions(
    admin: AdminProfile = Depends(require_admin),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
) -> dict:
    rows, total = await session_uc.list_blind_sessions(
        admin_user_id=admin.id, limit=limit, offset=offset, status=status
    )
    return {
        "code": 0,
        "data": [r.model_dump(mode="json") for r in rows],
        "total": total,
    }


@protected.get("/rounds")
async def api_list_blind_rounds(
    admin: AdminProfile = Depends(require_admin),
    limit: int = Query(default=30, ge=1, le=100),
) -> dict:
    rounds = await session_uc.list_blind_rounds(admin_user_id=admin.id, limit=limit)
    return {"code": 0, "data": [r.model_dump(mode="json") for r in rounds]}


@protected.get("/sessions/{session_id}")
async def api_get_blind_session(
    session_id: UUID,
    admin: AdminProfile = Depends(require_admin),
    period: str | None = Query(default=None, max_length=16),
) -> dict:
    out = await session_uc.get_blind_session(
        admin_user_id=admin.id, session_id=session_id, view_period=period
    )
    return {"code": 0, "data": out.model_dump(mode="json")}


@protected.post("/sessions/{session_id}/actions")
async def api_submit_blind_action(
    session_id: UUID,
    body: BlindActionIn,
    admin: AdminProfile = Depends(require_admin),
) -> dict:
    out = await action_uc.submit_blind_action(
        admin_user_id=admin.id,
        session_id=session_id,
        body=body,
    )
    return {"code": 0, "data": out.model_dump(mode="json")}


@protected.post("/sessions/{session_id}/finish")
async def api_finish_blind_session(
    session_id: UUID,
    admin: AdminProfile = Depends(require_admin),
    idempotency_key: str = Depends(_idem),
) -> dict:
    _ = idempotency_key
    out = await session_uc.finish_blind_session(
        admin_user_id=admin.id, session_id=session_id
    )
    return {"code": 0, "data": out.model_dump(mode="json")}


@protected.post("/sessions/{session_id}/skip")
async def api_skip_blind_session(
    session_id: UUID,
    admin: AdminProfile = Depends(require_admin),
    idempotency_key: str = Depends(_idem),
) -> dict:
    _ = idempotency_key
    out = await session_uc.skip_blind_session(admin_user_id=admin.id, session_id=session_id)
    return {"code": 0, "data": out.model_dump(mode="json")}


@protected.get("/consistency-report")
async def api_get_consistency_report(
    admin: AdminProfile = Depends(require_admin),
    period: str | None = Query(default=None),
) -> dict:
    out = await consistency_uc.get_consistency_report(
        admin_user_id=admin.id, period=period
    )
    return {"code": 0, "data": out.model_dump(mode="json")}


@protected.post("/consistency-report")
async def api_evaluate_consistency_report(
    admin: AdminProfile = Depends(require_admin),
    period: str | None = Query(default=None),
    regenerate: bool = Query(default=False),
) -> dict:
    out = await consistency_uc.evaluate_consistency_report(
        admin_user_id=admin.id,
        period=period,
        regenerate=regenerate,
    )
    return {"code": 0, "data": out.model_dump(mode="json")}


@protected.patch("/consistency-report/{report_id}")
async def api_patch_consistency_report(
    report_id: UUID,
    body: BlindConsistencyPatchIn,
    admin: AdminProfile = Depends(require_admin),
) -> dict:
    out = await consistency_uc.patch_consistency_corrections(
        admin_user_id=admin.id, report_id=report_id, body=body
    )
    return {"code": 0, "data": out.model_dump(mode="json")}


router.include_router(protected)
