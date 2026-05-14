"""通达信 ``connect.cfg`` 解析器。

通达信桌面客户端会把行情主站、扩展行情、资讯主站记录在 ``connect.cfg`` 这个文本配置里，
真实文件常见两类写法（同一个文件甚至会混用）：

1. **分组多行式**（最常见，主体由通达信生成）::

       [HQHOST]
       HostNum=8
       HostName00=深圳主站1
       IPAddress00=119.147.212.81
       Port00=7709
       HostName01=...
       ...

   分组段通常分别叫 ``[HQHOST]``（行情）、``[HQEX_HOST]``（扩展行情，多为 7727）、
   ``[INFO_HOST]``（资讯主站）等。本解析器**只解析出 IP+端口+名称**，**不**按段过滤；
   是否只保留 7709/7708 等行情口由调用方决定。

2. **单行混写式**（用户手工编辑、社区版客户端常见）::

       HQ00=深圳主站1,119.147.212.81:7709
       119.147.212.82,7709,深圳主站2
       # 注释
       ; 注释

   字段顺序不固定，但每行通常能匹配出一个 IPv4 + 端口。

为兼容上述两类写法，解析器先尝试聚合 ``HostName/IPAddress/Port`` 三元组，
若一个分组段里没有抽出任何主机，再退回到逐行正则兜底。

参考实现：``HQScanner.app.services.tdx_host_service.parse_connect_cfg``。
"""
from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Iterable

from .host_manager import TdxHost

logger = logging.getLogger(__name__)

# 三元组键的正则：HostName00= / IPAddress00= / Port00= ，编号通常 2 位，也兼容 1~3 位
_RE_TRIPLE_KEY = re.compile(
    r"^(HostName|IPAddress|Port)(\d{1,3})\s*=\s*(.+?)\s*$",
    re.IGNORECASE,
)

# 段头：[HQHOST] / [HQEX_HOST] / [INFO_HOST] ...
_RE_SECTION = re.compile(r"^\s*\[(.+?)\]\s*$")

# 单行兜底：从一行任意位置抽出 IPv4 与端口（端口必须紧邻 IP，允许 `,` `:` 空格做分隔）
_RE_IP_PORT = re.compile(
    r"\b((?:\d{1,3}\.){3}\d{1,3})\s*[,:\s]+\s*(\d{2,5})\b",
)


def _normalize_text(content: str | bytes) -> str:
    """统一处理 BOM、编码兜底，输出 ``str``。"""
    if isinstance(content, bytes):
        text = decode_bytes(content)
    else:
        text = content
    return text.lstrip("\ufeff")


def decode_bytes(raw: bytes) -> str:
    """按 utf-8-sig / utf-8 / gbk / gb2312 / latin-1 顺序尝试解码。

    通达信 ``connect.cfg`` 在 Windows 中文系统下常见 GBK 编码，国内分发的客户端偶尔会
    带 BOM 的 UTF-8。``latin-1`` 是最后兜底，确保不会因为单字节非法序列把整行丢掉。
    """
    for enc in ("utf-8-sig", "utf-8", "gbk", "gb2312", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    # 理论上不可达：latin-1 能解码任何字节序列
    return raw.decode("latin-1", errors="replace")


def _valid_port(s: str) -> int | None:
    try:
        p = int(s)
    except (TypeError, ValueError):
        return None
    return p if 1 <= p <= 65535 else None


def _valid_ipv4(s: str) -> bool:
    parts = s.split(".")
    if len(parts) != 4:
        return False
    for p in parts:
        if not p.isdigit():
            return False
        v = int(p)
        if v < 0 or v > 255:
            return False
    return True


def parse_connect_cfg(content: str | bytes) -> list[TdxHost]:
    """解析 ``connect.cfg`` 内容，返回去重后的主站列表。

    - 同一 ``(ip, port)`` 只保留第一次出现。
    - 不按段过滤；即使是 ``[HQEX_HOST]`` 的 7727 主站也会返回，由上层决定取舍。
    - 名称缺失时回退为 ``{ip}:{port}``。
    """
    text = _normalize_text(content)

    by_section: dict[str, dict[str, dict[str, str]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    current_section = "DEFAULT"
    raw_lines: list[str] = []

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        m_sec = _RE_SECTION.match(line)
        if m_sec:
            current_section = m_sec.group(1).strip().upper()
            continue
        m_triple = _RE_TRIPLE_KEY.match(line)
        if m_triple:
            kind, idx, value = m_triple.groups()
            by_section[current_section][idx][kind.lower()] = value.strip()
            continue
        raw_lines.append(line)

    hosts: list[TdxHost] = []
    seen: set[tuple[str, int]] = set()

    def _push(ip: str, port: int, name: str) -> None:
        key = (ip, port)
        if key in seen:
            return
        seen.add(key)
        hosts.append(TdxHost(ip=ip, port=port, name=name or f"{ip}:{port}"))

    # ── 1) 多行三元组路径 ────────────────────────────────────────────────────────
    for section, group in by_section.items():
        for idx, fields in sorted(group.items()):
            ip = fields.get("ipaddress", "").strip()
            port = _valid_port(fields.get("port", ""))
            name = fields.get("hostname", "").strip()
            if not ip or port is None or not _valid_ipv4(ip):
                continue
            _push(ip, port, name)
        logger.debug(
            "tdx_cfg_section_parsed",
            extra={"section": section, "count": len(group)},
        )

    # ── 2) 单行兜底（含上面分组段内没法配齐三元组的剩余行）──────────────────────
    for line in raw_lines:
        for ip, port_s in _RE_IP_PORT.findall(line):
            port = _valid_port(port_s)
            if port is None or not _valid_ipv4(ip):
                continue
            # 名称推断：取该行去掉 ip/port 后剩余的"看着像名称"的片段
            residual = _RE_IP_PORT.sub(" ", line)
            # 去掉前缀 KEY= 与连接符
            residual = re.sub(r"^\s*[\w\.]+\s*=\s*", "", residual)
            name = re.sub(r"[,:;\s]+", " ", residual).strip()
            _push(ip, port, name)

    logger.info("tdx_cfg_parsed", extra={"hosts": len(hosts)})
    return hosts


def filter_quote_hosts(
    hosts: Iterable[TdxHost],
    *,
    allowed_ports: tuple[int, ...] = (7709, 7708),
) -> list[TdxHost]:
    """从混合主站列表里只保留行情口（默认 7709/7708）。

    扩展行情 7727 / 资讯主站等不返回 K 线，留着只会拖慢测速并误导调用方。
    """
    return [h for h in hosts if h.port in allowed_ports]
