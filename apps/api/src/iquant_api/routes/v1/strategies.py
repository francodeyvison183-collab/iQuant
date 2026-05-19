"""行为策略 REST（迭代 V0.2a）。"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, Field

from iquant_domain.errors import ValidationError
from iquant_identity_service.usecases.schemas import AdminProfile
from iquant_strategy_service.usecases import strategies as strategy_uc
from iquant_strategy_service.usecases.schemas import StrategyGenerateIn

from ...deps import require_admin

router = APIRouter(
    prefix="/strategies",
    tags=["strategies"],
    dependencies=[Depends(require_admin)],
)


def _idem(x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key")) -> str:
    if not x_idempotency_key or len(x_idempotency_key.strip()) < 8:
        raise ValidationError("请求头 X-Idempotency-Key 必填且至少 8 字符")
    return x_idempotency_key.strip()[:128]


class ConfirmBody(BaseModel):
    version_id: UUID = Field(...)


@router.post("/generate")
async def api_generate_strategies(
    body: StrategyGenerateIn,
    admin: AdminProfile = Depends(require_admin),
    idempotency_key: str = Depends(_idem),
) -> dict:
    out = await strategy_uc.generate_from_blind(
        admin_user_id=admin.id,
        body=body,
        idempotency_key=idempotency_key,
    )
    return {"code": 0, "data": out.model_dump(mode="json")}


@router.get("")
async def api_list_strategies(
    admin: AdminProfile = Depends(require_admin),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    rows, total = await strategy_uc.list_strategies(
        admin_user_id=admin.id, limit=limit, offset=offset
    )
    return {
        "code": 0,
        "data": [r.model_dump(mode="json") for r in rows],
        "total": total,
    }


@router.get("/{strategy_id}")
async def api_get_strategy(
    strategy_id: UUID,
    admin: AdminProfile = Depends(require_admin),
) -> dict:
    out = await strategy_uc.get_strategy(admin_user_id=admin.id, strategy_id=strategy_id)
    return {"code": 0, "data": out.model_dump(mode="json")}


@router.post("/{strategy_id}/confirm")
async def api_confirm_strategy(
    strategy_id: UUID,
    body: ConfirmBody,
    admin: AdminProfile = Depends(require_admin),
    idempotency_key: str = Depends(_idem),
) -> dict:
    _ = idempotency_key
    out = await strategy_uc.confirm_strategy_version(
        admin_user_id=admin.id,
        strategy_id=strategy_id,
        version_id=body.version_id,
    )
    return {"code": 0, "data": out.model_dump(mode="json")}
