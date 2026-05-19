"""审计日志仓储。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AdminAuditLogORM, AdminUserORM


class AdminAuditRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def append(
        self,
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
        self.s.add(
            AdminAuditLogORM(
                admin_user_id=admin_user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                method=method,
                path=path,
                status_code=status_code,
                ip=ip,
                user_agent=user_agent[:512],
                request_id=request_id,
                detail=detail or {},
            )
        )
        await self.s.flush()

    async def list_paged(
        self,
        *,
        action: str | None = None,
        path_contains: str | None = None,
        admin_user_id: int | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[tuple[AdminAuditLogORM, str | None]], int]:
        q = (
            select(AdminAuditLogORM, AdminUserORM.username)
            .outerjoin(AdminUserORM, AdminAuditLogORM.admin_user_id == AdminUserORM.id)
            .order_by(AdminAuditLogORM.created_at.desc())
        )
        c = select(func.count()).select_from(AdminAuditLogORM)
        if action:
            q = q.where(AdminAuditLogORM.action == action)
            c = c.where(AdminAuditLogORM.action == action)
        if path_contains:
            q = q.where(AdminAuditLogORM.path.ilike(f"%{path_contains}%"))
            c = c.where(AdminAuditLogORM.path.ilike(f"%{path_contains}%"))
        if admin_user_id is not None:
            q = q.where(AdminAuditLogORM.admin_user_id == admin_user_id)
            c = c.where(AdminAuditLogORM.admin_user_id == admin_user_id)
        if since is not None:
            q = q.where(AdminAuditLogORM.created_at >= since)
            c = c.where(AdminAuditLogORM.created_at >= since)
        if until is not None:
            q = q.where(AdminAuditLogORM.created_at <= until)
            c = c.where(AdminAuditLogORM.created_at <= until)
        rows = (await self.s.execute(q.limit(limit).offset(offset))).all()
        total = int((await self.s.execute(c)).scalar_one())
        return [(r[0], r[1]) for r in rows], total
