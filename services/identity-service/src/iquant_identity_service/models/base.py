"""业务主库 ORM 基类（与 market-service 共用同一 PostgreSQL 实例）。"""
from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class PgBase(DeclarativeBase):
    """业务主库 ORM 基类。"""
