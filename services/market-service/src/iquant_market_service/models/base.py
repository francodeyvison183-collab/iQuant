"""ORM 基类：业务主库（PG）与时序行情库（TS）使用不同 metadata，避免 Alembic 误识别。"""
from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class PgBase(DeclarativeBase):
    """业务主库 ORM 基类。"""


class TsBase(DeclarativeBase):
    """时序行情库 ORM 基类（TimescaleDB）。"""
