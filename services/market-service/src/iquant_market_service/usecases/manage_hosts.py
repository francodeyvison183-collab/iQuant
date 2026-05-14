"""TDX 主站管理用例。

数据双写：
- 配置文件（``storage/local/tdx_hosts.json``）作为运行时连接池读取源
- 数据库 ``tdx_host`` 表作为审计与后台编辑入口

主站测速结果以测速时间为准回写到这两处。
"""
from __future__ import annotations

import logging

from iquant_market_data.tdx.cfg_parser import (
    decode_bytes,
    filter_quote_hosts,
    parse_connect_cfg,
)
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


async def import_hosts_from_cfg(
    raw: bytes,
    *,
    only_quote_ports: bool = True,
    run_test: bool = True,
) -> dict:
    """从上传的 ``connect.cfg`` 内容批量导入主站。

    流程：
    1. 解析（多编码兜底） → ``parse_connect_cfg`` → ``list[TdxHost]``
    2. ``only_quote_ports`` 默认仅保留 7709/7708，过滤掉扩展行情 / 资讯主站
    3. 与现有主站合并去重（按 ``ip:port``）；新增条目同时写入 JSON 配置和 ``tdx_host`` 表
    4. ``run_test=True`` 时立即触发一次全量测速

    返回 ``{parsed, kept, added, total, hosts}``，便于前端展示导入结果。
    """
    text = decode_bytes(raw)
    parsed = parse_connect_cfg(text)
    kept = filter_quote_hosts(parsed) if only_quote_ports else list(parsed)

    hm = _build_manager()
    hm.load()
    existing_keys = {(h.ip, h.port) for h in hm.hosts}

    added: list[TdxHost] = []
    for new_host in kept:
        key = (new_host.ip, new_host.port)
        if key in existing_keys:
            continue
        try:
            host = hm.add(ip=new_host.ip, port=new_host.port, name=new_host.name)
        except ValueError:
            # 并发情况下偶发"已存在"——直接跳过
            continue
        existing_keys.add(key)
        added.append(host)

    async with pg_session() as ses:
        repo = TdxHostRepo(ses)
        await repo.seed_defaults()
        for h in added:
            try:
                await repo.add(ip=h.ip, port=h.port, name=h.name)
            except Exception:
                # 唯一约束冲突属正常情况：cfg 里的 ip:port 可能已经被早先的 add 或 seed_defaults 写入。
                await ses.rollback()
                continue
        await ses.commit()

    hosts_after = await test_hosts() if run_test else hm.hosts

    logger.info(
        "tdx_cfg_imported",
        extra={
            "parsed": len(parsed),
            "kept": len(kept),
            "added": len(added),
            "total": len(hosts_after),
            "only_quote_ports": only_quote_ports,
            "run_test": run_test,
        },
    )
    return {
        "parsed": len(parsed),
        "kept": len(kept),
        "added": len(added),
        "total": len(hosts_after),
        "hosts": [h.to_dict() for h in hosts_after],
    }
