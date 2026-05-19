"""管理员登录、刷新、退出。"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from iquant_domain.errors import AuthError, RateLimitedError, ServiceUnavailableError, ValidationError
from redis.exceptions import RedisError

from ..config import get_identity_settings
from ..crypto import hash_refresh_token, new_refresh_token, verify_password
from ..db import pg_session
from ..jwt_tokens import create_access_token, decode_access_token
from ..redis_client import (
    clear_login_failures,
    get_redis,
    is_access_jti_revoked,
    is_ip_locked,
    rate_limit_hit,
    record_login_failure,
    revoke_access_jti,
)
from ..repositories.admin_audit_repo import AdminAuditRepo
from ..repositories.admin_refresh_token_repo import AdminRefreshTokenRepo
from ..repositories.admin_user_repo import AdminUserRepo
from ..turnstile import verify_turnstile
from .schemas import AdminProfile, LoginResult


def _profile(row) -> AdminProfile:  # type: ignore[no-untyped-def]
    return AdminProfile(
        id=row.id,
        username=row.username,
        display_name=row.display_name or row.username,
        must_change_password=row.password_changed_at is None,
        last_login_at=row.last_login_at,
    )


async def _redis_guard() -> None:
    """登录限流依赖 Redis；不可用时返回明确 503，避免裸 500。"""
    try:
        r = await get_redis()
        await r.ping()
    except RedisError as exc:
        raise ServiceUnavailableError(
            "认证服务暂不可用（Redis），请确认 docker compose 已启动 redis 服务"
        ) from exc


async def login(
    *,
    username: str,
    password: str,
    ip: str,
    user_agent: str,
    captcha_token: str,
) -> LoginResult:
    settings = get_identity_settings()
    await _redis_guard()
    try:
        locked, ttl = await is_ip_locked(ip)
        if locked:
            raise RateLimitedError(f"登录尝试过多，请 {ttl} 秒后再试")

        allowed, retry = await rate_limit_hit(
            key=f"admin:login:ip:{ip}",
            limit=settings.login_rate_limit_per_minute,
            window_seconds=60,
        )
    except RedisError as exc:
        raise ServiceUnavailableError(
            "认证服务暂不可用（Redis），请确认 docker compose 已启动 redis 服务"
        ) from exc
    if not allowed:
        raise RateLimitedError(f"请求过于频繁，请 {retry} 秒后再试")

    if not await verify_turnstile(token=captcha_token, remote_ip=ip):
        raise ValidationError("人机验证失败")

    async with pg_session() as ses:
        user = await AdminUserRepo(ses).get_by_username(username.strip())
        ok = user is not None and user.is_active and verify_password(user.password_hash, password)
        if not ok:
            await AdminAuditRepo(ses).append(
                admin_user_id=user.id if user else None,
                action="auth.login_failed",
                method="POST",
                path="/admin/auth/login",
                status_code=401,
                ip=ip,
                user_agent=user_agent,
                detail={"username": username},
            )
            await ses.commit()
            await record_login_failure(
                ip,
                threshold=settings.login_fail_lock_threshold,
                lock_seconds=settings.login_fail_lock_seconds,
            )
            raise AuthError("用户名或密码错误", code="AUTH_INVALID")

        access, jti, exp = create_access_token(admin_user_id=user.id, username=user.username)
        refresh_plain = new_refresh_token()
        refresh_hash = hash_refresh_token(refresh_plain)
        refresh_exp = datetime.now(tz=UTC) + timedelta(days=settings.admin_refresh_token_days)
        await AdminRefreshTokenRepo(ses).create(
            admin_user_id=user.id,
            token_hash=refresh_hash,
            expires_at=refresh_exp,
            ip=ip,
            user_agent=user_agent,
        )
        await AdminUserRepo(ses).update_login(user.id)
        await AdminAuditRepo(ses).append(
            admin_user_id=user.id,
            action="auth.login",
            method="POST",
            path="/admin/auth/login",
            status_code=200,
            ip=ip,
            user_agent=user_agent,
        )
        await ses.commit()

    await clear_login_failures(ip)
    return LoginResult(
        access_token=access,
        refresh_token=refresh_plain,
        expires_at=exp,
        admin=_profile(user),
    )


async def refresh_session(*, refresh_token: str, ip: str, user_agent: str) -> LoginResult:
    settings = get_identity_settings()
    token_hash = hash_refresh_token(refresh_token)
    async with pg_session() as ses:
        row = await AdminRefreshTokenRepo(ses).get_valid(token_hash)
        if row is None:
            raise AuthError("会话已失效，请重新登录", code="AUTH_EXPIRED")
        user = await AdminUserRepo(ses).get_by_id(row.admin_user_id)
        if user is None or not user.is_active:
            raise AuthError("账号不可用", code="AUTH_INVALID")

        await AdminRefreshTokenRepo(ses).revoke(token_hash)
        access, jti, exp = create_access_token(admin_user_id=user.id, username=user.username)
        refresh_plain = new_refresh_token()
        new_hash = hash_refresh_token(refresh_plain)
        refresh_exp = datetime.now(tz=UTC) + timedelta(days=settings.admin_refresh_token_days)
        await AdminRefreshTokenRepo(ses).create(
            admin_user_id=user.id,
            token_hash=new_hash,
            expires_at=refresh_exp,
            ip=ip,
            user_agent=user_agent,
        )
        await ses.commit()

    return LoginResult(
        access_token=access,
        refresh_token=refresh_plain,
        expires_at=exp,
        admin=_profile(user),
    )


async def logout(*, refresh_token: str, access_token: str | None = None) -> None:
    token_hash = hash_refresh_token(refresh_token)
    async with pg_session() as ses:
        row = await AdminRefreshTokenRepo(ses).get_valid(token_hash)
        admin_id = row.admin_user_id if row else None
        await AdminRefreshTokenRepo(ses).revoke(token_hash)
        await AdminAuditRepo(ses).append(
            admin_user_id=admin_id,
            action="auth.logout",
            method="POST",
            path="/admin/auth/logout",
            status_code=200,
        )
        await ses.commit()

    if access_token:
        try:
            payload = decode_access_token(access_token)
            jti = str(payload.get("jti", ""))
            exp = payload.get("exp")
            if jti and exp:
                ttl = int(exp) - int(datetime.now(tz=UTC).timestamp())
                await revoke_access_jti(jti, max(ttl, 1))
        except Exception:  # noqa: BLE001
            pass


async def get_admin_profile(admin_id: int) -> AdminProfile:
    async with pg_session() as ses:
        user = await AdminUserRepo(ses).get_by_id(admin_id)
    if user is None or not user.is_active:
        raise AuthError("账号不可用", code="AUTH_INVALID")
    return _profile(user)


async def verify_access_token(token: str) -> AdminProfile:
    try:
        payload = decode_access_token(token)
    except Exception as exc:  # noqa: BLE001
        raise AuthError("无效的访问令牌", code="AUTH_INVALID") from exc
    if payload.get("typ") != "admin_access":
        raise AuthError("无效的访问令牌", code="AUTH_INVALID")
    jti = str(payload.get("jti", ""))
    if jti and await is_access_jti_revoked(jti):
        raise AuthError("访问令牌已吊销", code="AUTH_EXPIRED")
    admin_id = int(payload["sub"])
    return await get_admin_profile(admin_id)


async def change_password(*, admin_id: int, old_password: str, new_password: str) -> None:
    from ..crypto import hash_password

    if len(new_password) < 8:
        raise ValidationError("新密码至少 8 位")
    async with pg_session() as ses:
        user = await AdminUserRepo(ses).get_by_id(admin_id)
        if user is None or not verify_password(user.password_hash, old_password):
            raise AuthError("原密码错误", code="AUTH_INVALID")
        await AdminUserRepo(ses).update_password(admin_id, hash_password(new_password))
        await AdminAuditRepo(ses).append(
            admin_user_id=admin_id,
            action="admin.password.change",
            method="PATCH",
            path="/admin/auth/password",
            status_code=200,
        )
        await ses.commit()
