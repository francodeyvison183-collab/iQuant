"""管理员 Access JWT。"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt

from .config import get_identity_settings


def create_access_token(*, admin_user_id: int, username: str) -> tuple[str, str, datetime]:
    settings = get_identity_settings()
    jti = uuid.uuid4().hex
    exp = datetime.now(tz=UTC) + timedelta(minutes=settings.admin_access_token_minutes)
    payload = {
        "sub": str(admin_user_id),
        "username": username,
        "jti": jti,
        "exp": exp,
        "iat": datetime.now(tz=UTC),
        "typ": "admin_access",
    }
    token = jwt.encode(payload, settings.admin_jwt_secret, algorithm="HS256")
    return token, jti, exp


def decode_access_token(token: str) -> dict:
    settings = get_identity_settings()
    return jwt.decode(
        token,
        settings.admin_jwt_secret,
        algorithms=["HS256"],
        options={"require": ["exp", "sub", "jti", "typ"]},
    )
