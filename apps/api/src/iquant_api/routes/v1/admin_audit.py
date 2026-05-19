"""管理员审计日志查询。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from iquant_identity_service.usecases.audit import list_audit_logs
from iquant_identity_service.usecases.schemas import AdminProfile

from ...deps import require_admin

router = APIRouter(prefix="/admin/audit-logs", tags=["admin-audit"], dependencies=[Depends(require_admin)])


@router.get("")
async def api_list_audit_logs(
    action: str | None = Query(default=None),
    path_contains: str | None = Query(default=None),
    admin_user_id: int | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=90),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    rows, total = await list_audit_logs(
        action=action,
        path_contains=path_contains,
        admin_user_id=admin_user_id,
        days=days,
        limit=limit,
        offset=offset,
    )
    return {
        "code": 0,
        "data": [r.model_dump(mode="json") for r in rows],
        "total": total,
    }
