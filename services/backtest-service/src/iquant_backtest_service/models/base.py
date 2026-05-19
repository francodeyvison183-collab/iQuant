"""ORM 基类。"""
from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class PgBase(DeclarativeBase):
    """业务主库。"""
