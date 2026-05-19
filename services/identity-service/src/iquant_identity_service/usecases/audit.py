"""审计日志用例。"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ..db import pg_session
from ..repositories.admin_audit_repo import AdminAuditRepo
from .schemas import AuditLogRow


async def append_audit_log(
    *,
    admin_user_id: int | None,
    action: str,
    resource_type: str = "",
    resource_id: str = "",
    method: str = "",
    path: str = "",
    status_code: int = 0,
    ip: str = "",
    user_agent: str = "",
    request_id: str = "",
    detail: dict | None = None,
) -> None:
    async with pg_session() as ses:
        await AdminAuditRepo(ses).append(
            admin_user_id=admin_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            method=method,
            path=path,
            status_code=status_code,
            ip=ip,
            user_agent=user_agent,
            request_id=request_id,
            detail=detail,
        )
        await ses.commit()


async def list_audit_logs(
    *,
    action: str | None = None,
    path_contains: str | None = None,
    admin_user_id: int | None = None,
    days: int = 30,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AuditLogRow], int]:
    since = datetime.now(tz=UTC) - timedelta(days=max(days, 1))
    async with pg_session() as ses:
        rows, total = await AdminAuditRepo(ses).list_paged(
            action=action,
            path_contains=path_contains,
            admin_user_id=admin_user_id,
            since=since,
            limit=limit,
            offset=offset,
        )
    items = [
        AuditLogRow(
            id=log.id,
            admin_user_id=log.admin_user_id,
            username=username,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            method=log.method,
            path=log.path,
            status_code=log.status_code,
            ip=log.ip,
            user_agent=log.user_agent,
            request_id=log.request_id,
            detail=dict(log.detail or {}),
            created_at=log.created_at,
        )
        for log, username in rows
    ]
    return items, total
