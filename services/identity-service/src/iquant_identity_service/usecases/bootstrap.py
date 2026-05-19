"""首个管理员种子。"""
from __future__ import annotations

from iquant_domain.errors import ValidationError

from ..config import get_identity_settings
from ..crypto import hash_password
from ..db import pg_session
from ..repositories.admin_user_repo import AdminUserRepo


async def bootstrap_admin(*, username: str | None = None, password: str | None = None) -> dict:
    settings = get_identity_settings()
    uname = (username or settings.admin_bootstrap_username).strip()
    pwd = password or settings.admin_bootstrap_password
    if not uname or not pwd:
        raise ValidationError("需提供 IQUANT_ADMIN_BOOTSTRAP_USERNAME 与 IQUANT_ADMIN_BOOTSTRAP_PASSWORD")
    if len(pwd) < 8:
        raise ValidationError("密码至少 8 位")

    async with pg_session() as ses:
        repo = AdminUserRepo(ses)
        if await repo.count() > 0:
            raise ValidationError("已存在管理员，拒绝重复 bootstrap")
        if await repo.get_by_username(uname) is not None:
            raise ValidationError(f"用户名已存在: {uname}")
        row = await repo.create(
            username=uname,
            password_hash=hash_password(pwd),
            display_name=uname,
        )
        await ses.commit()
    return {"username": uname, "admin_id": row.id}
