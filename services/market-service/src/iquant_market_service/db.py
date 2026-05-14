"""SQLAlchemy 异步引擎与 Session 工厂（业务主库 + 时序行情库）。"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .config import get_market_settings

_pg_engine: AsyncEngine | None = None
_pg_session_factory: async_sessionmaker[AsyncSession] | None = None
_ts_engine: AsyncEngine | None = None
_ts_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_pg_engine() -> AsyncEngine:
    global _pg_engine
    if _pg_engine is None:
        s = get_market_settings()
        _pg_engine = create_async_engine(
            s.pg_dsn,
            pool_size=10,
            max_overflow=10,
            pool_pre_ping=True,
        )
    return _pg_engine


def get_pg_session_factory() -> async_sessionmaker[AsyncSession]:
    global _pg_session_factory
    if _pg_session_factory is None:
        _pg_session_factory = async_sessionmaker(
            bind=get_pg_engine(), expire_on_commit=False, autoflush=False
        )
    return _pg_session_factory


def get_ts_engine() -> AsyncEngine:
    global _ts_engine
    if _ts_engine is None:
        s = get_market_settings()
        _ts_engine = create_async_engine(
            s.ts_dsn,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )
    return _ts_engine


def get_ts_session_factory() -> async_sessionmaker[AsyncSession]:
    global _ts_session_factory
    if _ts_session_factory is None:
        _ts_session_factory = async_sessionmaker(
            bind=get_ts_engine(), expire_on_commit=False, autoflush=False
        )
    return _ts_session_factory


@asynccontextmanager
async def pg_session() -> AsyncIterator[AsyncSession]:
    async with get_pg_session_factory()() as s:
        yield s


@asynccontextmanager
async def ts_session() -> AsyncIterator[AsyncSession]:
    async with get_ts_session_factory()() as s:
        yield s
