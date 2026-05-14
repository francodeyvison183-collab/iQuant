"""健康检查。"""
from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from iquant_market_service.db import get_pg_engine, get_ts_engine

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict:
    """进程存活检查。"""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz() -> dict:
    """依赖就绪检查：业务主库 + 时序库可达。"""
    checks = {"postgres": False, "timescaledb": False}
    try:
        async with get_pg_engine().connect() as conn:
            await conn.execute(text("select 1"))
            checks["postgres"] = True
    except Exception:
        pass
    try:
        async with get_ts_engine().connect() as conn:
            await conn.execute(text("select 1"))
            checks["timescaledb"] = True
    except Exception:
        pass
    status = "ok" if all(checks.values()) else "degraded"
    return {"status": status, "checks": checks}
