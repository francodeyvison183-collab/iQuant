"""目录扫描测试。"""
from __future__ import annotations

import struct
from pathlib import Path

import pytest

from iquant_market_data.tdx.file_scanner import scan_changed_files, scan_tdx_files


def _write_fake_day(path: Path, count: int = 3) -> None:
    """写入一个 minimal 合法 .day 文件（32 字节定长记录）。

    布局：date(4) open(4) high(4) low(4) close(4) amount(4,float) volume(4) reserved(4) = 32
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fmt = struct.Struct("<iiiiifii")  # 5*int + float + 2*int = 8*4 = 32
    assert fmt.size == 32
    blob = b"".join(
        fmt.pack(20260101 + i, 1000, 1100, 900, 1050, 1234.5, 10000, 0)
        for i in range(count)
    )
    path.write_bytes(blob)


def test_scan_empty_returns_empty(tmp_path: Path):
    assert scan_tdx_files(str(tmp_path)) == []


def test_scan_finds_day_file(tmp_path: Path):
    sh_day = tmp_path / "sh" / "lday" / "sh600519.day"
    _write_fake_day(sh_day, 5)
    files = scan_tdx_files(str(tmp_path))
    assert len(files) == 1
    f = files[0]
    assert f.full_code == "sh600519"
    assert f.market.value == "sh"
    assert f.code == "600519"
    assert f.period.value == "day"


def test_scan_filters_unsupported_code(tmp_path: Path):
    bad = tmp_path / "sh" / "lday" / "sh000001.day"  # sh 不接受 0xx 开头
    _write_fake_day(bad, 1)
    assert scan_tdx_files(str(tmp_path)) == []


def test_scan_changed_files(tmp_path: Path):
    sh_day = tmp_path / "sh" / "lday" / "sh600519.day"
    _write_fake_day(sh_day, 3)

    changed, unchanged = scan_changed_files(str(tmp_path), state_map={})
    assert len(changed) == 1 and not unchanged

    # 用当前 state 重扫，应进入 unchanged
    fi = changed[0]
    state_map = {fi.file_path: fi.signature}
    changed2, unchanged2 = scan_changed_files(str(tmp_path), state_map=state_map)
    assert not changed2
    assert len(unchanged2) == 1
