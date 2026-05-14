"""``connect.cfg`` 解析器单元测试。

只覆盖纯解析逻辑，不涉及网络与文件系统。
"""
from __future__ import annotations

import pytest

from iquant_market_data.tdx.cfg_parser import (
    decode_bytes,
    filter_quote_hosts,
    parse_connect_cfg,
)


def test_parse_multi_line_section() -> None:
    """通达信原生 connect.cfg 的标准多行格式。"""
    content = """
[HQHOST]
HostNum=3
HostName00=深圳主站1
IPAddress00=119.147.212.81
Port00=7709
HostName01=广州主站1
IPAddress01=14.215.177.9
Port01=7709
HostName02=上海主站1
IPAddress02=101.227.77.254
Port02=7709
"""
    hosts = parse_connect_cfg(content)
    addresses = {(h.ip, h.port) for h in hosts}
    assert ("119.147.212.81", 7709) in addresses
    assert ("14.215.177.9", 7709) in addresses
    assert ("101.227.77.254", 7709) in addresses
    names = {h.name for h in hosts}
    assert "深圳主站1" in names


def test_parse_single_line_fallback() -> None:
    """社区版 / 用户自编辑常见的单行格式。"""
    content = """
# 注释
; 另一种注释
HQ00=深圳主站1,119.147.212.81:7709
119.147.212.82,7709,深圳主站2
HQ02=14.215.177.9:7709,广州主站1
"""
    hosts = parse_connect_cfg(content)
    addresses = {(h.ip, h.port) for h in hosts}
    assert ("119.147.212.81", 7709) in addresses
    assert ("119.147.212.82", 7709) in addresses
    assert ("14.215.177.9", 7709) in addresses


def test_parse_dedup_and_section_isolation() -> None:
    """同 IP:Port 只保留一次；不同段也参与去重。"""
    content = """
[HQHOST]
HostName00=A
IPAddress00=1.2.3.4
Port00=7709
[HQEX_HOST]
HostName00=ExA
IPAddress00=1.2.3.4
Port00=7727
[HQHOST_DUP]
HostName00=A-dup
IPAddress00=1.2.3.4
Port00=7709
"""
    hosts = parse_connect_cfg(content)
    addresses = [(h.ip, h.port) for h in hosts]
    assert addresses.count(("1.2.3.4", 7709)) == 1
    assert addresses.count(("1.2.3.4", 7727)) == 1


def test_parse_invalid_ip_or_port_skipped() -> None:
    content = """
[HQHOST]
HostName00=BadIP
IPAddress00=999.0.0.1
Port00=7709
HostName01=BadPort
IPAddress01=1.2.3.4
Port01=99999
HostName02=Good
IPAddress02=5.6.7.8
Port02=7709
"""
    hosts = parse_connect_cfg(content)
    addresses = {(h.ip, h.port) for h in hosts}
    assert ("5.6.7.8", 7709) in addresses
    assert ("999.0.0.1", 7709) not in addresses
    assert ("1.2.3.4", 99999) not in addresses


def test_parse_handles_bom_and_gbk() -> None:
    """UTF-8 BOM 应被吃掉；GBK 编码字节流应正确解码。"""
    text = "[HQHOST]\nHostName00=深圳主站\nIPAddress00=1.2.3.4\nPort00=7709\n"
    bom_bytes = ("\ufeff" + text).encode("utf-8")
    gbk_bytes = text.encode("gbk")
    for raw in (bom_bytes, gbk_bytes):
        hosts = parse_connect_cfg(raw)
        assert any(h.ip == "1.2.3.4" and h.port == 7709 for h in hosts)
        assert any("深圳" in h.name for h in hosts)


def test_filter_quote_hosts() -> None:
    content = """
[HQHOST]
HostName00=quote
IPAddress00=1.1.1.1
Port00=7709
[HQEX_HOST]
HostName00=ex
IPAddress00=2.2.2.2
Port00=7727
"""
    hosts = parse_connect_cfg(content)
    kept = filter_quote_hosts(hosts)
    ports = {h.port for h in kept}
    assert 7709 in ports
    assert 7727 not in ports


def test_decode_bytes_falls_back_to_latin1() -> None:
    """无法识别的字节序列也必须能得到字符串，不应抛异常。"""
    raw = b"\x80\x81\x82HostName00=X\nIPAddress00=1.2.3.4\nPort00=7709\n"
    text = decode_bytes(raw)
    assert "1.2.3.4" in text


@pytest.mark.parametrize(
    "line,expected_ip,expected_port",
    [
        ("HQ00=深圳1,119.147.212.81:7709", "119.147.212.81", 7709),
        ("119.147.212.82  7709  深圳2", "119.147.212.82", 7709),
        ("HQ02 = 14.215.177.9 : 7709", "14.215.177.9", 7709),
    ],
)
def test_parse_single_line_variants(
    line: str, expected_ip: str, expected_port: int
) -> None:
    hosts = parse_connect_cfg(line)
    assert any(h.ip == expected_ip and h.port == expected_port for h in hosts)
