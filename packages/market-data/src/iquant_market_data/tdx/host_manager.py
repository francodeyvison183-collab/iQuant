"""通达信主站管理。

职责：
- 维护可用主站列表（内置默认值 + 持久化覆盖）
- 并发测速（经 pytdx 连接握手）
- 按延迟选择最快主站，连续失败的非默认主站自动淘汰
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# 内置默认主站列表（社区常用的真实行情主站）
# 注意：7709/7708 为真实行情端口；7727 等扩展端口不提供 K 线。
DEFAULT_HOSTS: list[dict[str, object]] = [
    {"ip": "110.41.147.114", "port": 7709, "name": "腾讯云北京1"},
    {"ip": "119.147.212.81", "port": 7709, "name": "深圳主站1"},
    {"ip": "119.147.212.82", "port": 7709, "name": "深圳主站2"},
    {"ip": "14.215.177.9", "port": 7709, "name": "广州主站1"},
    {"ip": "14.215.177.38", "port": 7709, "name": "广州主站2"},
    {"ip": "101.227.77.254", "port": 7709, "name": "上海主站1"},
]

# 连续不可用超过该时长的非默认主站会被自动剔除
_AUTO_PRUNE = timedelta(hours=24)


@dataclass
class TdxHost:
    ip: str
    port: int
    name: str = ""
    status: str = "untested"  # untested | ok | fail
    speed_ms: int = 9999
    last_tested: str | None = None
    fail_since: str | None = None  # 首次连续失败时间字符串

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict[str, object]) -> "TdxHost":
        return TdxHost(
            ip=str(d["ip"]),
            port=int(d["port"]),  # type: ignore[arg-type]
            name=str(d.get("name") or f"{d['ip']}:{d['port']}"),
            status=str(d.get("status") or "untested"),
            speed_ms=int(d.get("speed_ms") or 9999),  # type: ignore[arg-type]
            last_tested=d.get("last_tested"),  # type: ignore[arg-type]
            fail_since=d.get("fail_since"),  # type: ignore[arg-type]
        )


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _probe_host(ip: str, port: int, timeout: float = 5.0) -> tuple[bool, int]:
    """同步测速：经 pytdx 完成连接握手，返回 (ok, elapsed_ms)。"""
    from .client import TdxClient

    start = time.perf_counter()
    client = TdxClient(ip, port, connect_timeout=timeout, read_timeout=timeout)
    try:
        client.connect()
        elapsed = int((time.perf_counter() - start) * 1000)
        return True, elapsed
    except Exception:  # noqa: BLE001
        return False, 9999
    finally:
        client.close()


@dataclass
class TdxHostManager:
    """通达信主站管理器。

    持久化文件路径默认在 ``config/tdx_hosts.json``；可由调用方指定。
    """

    config_path: Path
    hosts: list[TdxHost] = field(default_factory=list)

    # ── 持久化 ───────────────────────────────────────────────────────────────

    def load(self) -> list[TdxHost]:
        """从文件加载，文件不存在时返回内置默认值。"""
        if self.config_path.exists():
            try:
                raw = json.loads(self.config_path.read_text(encoding="utf-8"))
                self.hosts = [TdxHost.from_dict(h) for h in raw]
                if self.hosts:
                    logger.info("tdx_hosts_loaded", extra={"count": len(self.hosts)})
                    return self.hosts
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("tdx_hosts_load_failed", extra={"error": str(exc)})
        self.hosts = [TdxHost(**h) for h in DEFAULT_HOSTS]  # type: ignore[arg-type]
        return self.hosts

    def save(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps([h.to_dict() for h in self.hosts], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ── 编辑 ─────────────────────────────────────────────────────────────────

    def add(self, ip: str, port: int, name: str = "") -> TdxHost:
        for h in self.hosts:
            if h.ip == ip and h.port == port:
                raise ValueError(f"主站已存在: {ip}:{port}")
        host = TdxHost(ip=ip, port=port, name=name or f"{ip}:{port}")
        self.hosts.append(host)
        self.save()
        return host

    def remove(self, ip: str, port: int) -> bool:
        before = len(self.hosts)
        self.hosts = [h for h in self.hosts if not (h.ip == ip and h.port == port)]
        if len(self.hosts) != before:
            self.save()
            return True
        return False

    # ── 测速 ─────────────────────────────────────────────────────────────────

    async def test_all(self, timeout: float = 5.0) -> list[TdxHost]:
        """并发测速所有主站，更新状态后持久化并按速度排序返回。"""
        if not self.hosts:
            self.load()

        loop = asyncio.get_running_loop()

        async def _test(h: TdxHost) -> TdxHost:
            ok, elapsed = await loop.run_in_executor(None, _probe_host, h.ip, h.port, timeout)
            h.status = "ok" if ok else "fail"
            h.speed_ms = elapsed
            h.last_tested = _now_str()
            if ok:
                h.fail_since = None
            elif h.fail_since is None:
                h.fail_since = _now_str()
            return h

        await asyncio.gather(*[_test(h) for h in self.hosts])
        self._prune_stale()
        self.hosts.sort(key=lambda h: h.speed_ms)
        self.save()
        ok_count = sum(1 for h in self.hosts if h.status == "ok")
        logger.info(
            "tdx_hosts_tested",
            extra={"ok": ok_count, "total": len(self.hosts)},
        )
        return self.hosts

    def _prune_stale(self) -> None:
        default_addrs = {(h["ip"], int(h["port"])) for h in DEFAULT_HOSTS}  # type: ignore[arg-type]
        now = datetime.now()
        keep: list[TdxHost] = []
        for h in self.hosts:
            if h.fail_since and (h.ip, h.port) not in default_addrs:
                try:
                    fail_dt = datetime.strptime(h.fail_since, "%Y-%m-%d %H:%M:%S")
                    if now - fail_dt >= _AUTO_PRUNE:
                        logger.info("tdx_host_pruned", extra={"ip": h.ip, "port": h.port})
                        continue
                except ValueError:
                    pass
            keep.append(h)
        self.hosts = keep

    # ── 查询 ─────────────────────────────────────────────────────────────────

    def available(self, max_count: int | None = None) -> list[TdxHost]:
        """按延迟升序返回可用主站；未测速时回退到全量列表。"""
        ok = [h for h in self.hosts if h.status == "ok"]
        pool = sorted(ok, key=lambda h: h.speed_ms) if ok else list(self.hosts)
        return pool[:max_count] if max_count else pool

    def best(self) -> TdxHost | None:
        pool = self.available(max_count=1)
        return pool[0] if pool else None
