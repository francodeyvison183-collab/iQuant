"""本地 1 分钟 K 线解析。"""
from __future__ import annotations

import struct
from pathlib import Path

from iquant_domain.market import KlinePeriod
from iquant_market_data.tdx.file_parser import parse_lc1_file


def _write_lc1_bar(path: Path, year: int, month: int, day: int, hour: int, minute: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    date_enc = ((year - 2004) << 11) | (month * 100 + day)
    time_enc = hour * 60 + minute
    fmt = struct.Struct("<HHfffffii")
    path.write_bytes(
        fmt.pack(date_enc, time_enc, 10.0, 11.0, 9.0, 10.5, 1000.0, 100, 0)
    )


def test_parse_lc1_file(tmp_path: Path) -> None:
    f = tmp_path / "sh600519.lc1"
    _write_lc1_bar(f, 2024, 6, 1, 10, 30)
    bars = list(parse_lc1_file(str(f), full_code="sh600519"))
    assert len(bars) == 1
    assert bars[0].period == KlinePeriod.MIN_1
    assert bars[0].bar_time.hour == 10
    assert bars[0].bar_time.minute == 30
