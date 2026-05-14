"""TDX 主站管理用例。

数据双写：
- 配置文件（``storage/local/tdx_hosts.json``）作为运行时连接池读取源
- 数据库 ``tdx_host`` 表作为审计与后台编辑入口

主站测速结果以测速时间为准回写到这两处。
"""
from __future__ import annotations

import logging

from iquant_market_data.tdx.host_manager import TdxHost, TdxHostManager

from ..config import get_market_settings
from ..db import pg_session
from ..models import TdxHostORM
from ..repositories.tdx_host_repo import TdxHostRepo

logger = logging.getLogger(__name__)


def _build_manager() -> TdxHostManager:
    return TdxHostManager(config_path=get_market_settings().tdx_hosts_config)


async def list_hosts() -> list[dict]:
    """返回带数据库 id 的主站列表，便于前端按 id 删除。"""
    hm = _build_manager()
    hm.load()
    async with pg_session() as ses:
        repo = TdxHostRepo(ses)
        await repo.seed_defaults()
        await ses.commit()
        rows = await repo.list_all()
    json_by_addr = {(h.ip, h.port): h for h in hm.hosts}
    out: list[dict] = []
    for r in rows:
        j = json_by_addr.get((r.ip, r.port))
        out.append(
            {
                "id": r.id,
                "ip": r.ip,
                "port": r.port,
                "name": r.name,
                "is_builtin": r.is_builtin,
                "status": j.status if j else r.status,
                "speed_ms": j.speed_ms if j else r.speed_ms,
                "last_tested": j.last_tested
                if j
                else (r.last_tested.strftime("%Y-%m-%d %H:%M:%S") if r.last_tested else None),
                "fail_since": j.fail_since
                if j
                else (r.fail_since.strftime("%Y-%m-%d %H:%M:%S") if r.fail_since else None),
            }
        )
    return out


async def add_host(*, ip: str, port: int, name: str = "") -> TdxHost:
    hm = _build_manager()
    hm.load()
    host = hm.add(ip=ip, port=port, name=name)
    async with pg_session() as ses:
        await TdxHostRepo(ses).add(ip=ip, port=port, name=name or f"{ip}:{port}")
        await ses.commit()
    return host


async def remove_host(*, host_id: int) -> bool:
    """根据数据库 id 删除非内置主站。"""
    async with pg_session() as ses:
        repo = TdxHostRepo(ses)
        row = await ses.get(TdxHostORM, host_id)
        if row is None or row.is_builtin:
            return False
        ip, port = row.ip, row.port
        ok = await repo.remove(host_id)
        await ses.commit()
    if ok:
        hm = _build_manager()
        hm.load()
        hm.remove(ip, port)
    return ok


async def test_hosts() -> list[TdxHost]:
    hm = _build_manager()
    hm.load()
    hosts = await hm.test_all()
    # 同步结果到数据库（仅状态、速度、时间）
    async with pg_session() as ses:
        repo = TdxHostRepo(ses)
        await repo.seed_defaults()
        for h in hosts:
            await repo.update_test_result(
                ip=h.ip, port=h.port, status=h.status, speed_ms=h.speed_ms
            )
        await ses.commit()
    return hosts
