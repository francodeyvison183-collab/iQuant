"""鉴权密码与 token 烟测。"""
from __future__ import annotations

from iquant_identity_service.crypto import hash_password, hash_refresh_token, verify_password


def test_password_hash_roundtrip() -> None:
    h = hash_password("secure-pass-123")
    assert verify_password(h, "secure-pass-123")
    assert not verify_password(h, "wrong")


def test_refresh_token_hash_stable() -> None:
    assert hash_refresh_token("abc") == hash_refresh_token("abc")
