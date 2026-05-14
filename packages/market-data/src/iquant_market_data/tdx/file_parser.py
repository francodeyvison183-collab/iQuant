"""通达信本地行情文件解析。

文件均为 32 字节定长记录，按时间升序排列：

* ``.day``  日 K
    ``int32 date | int32 open | int32 high | int32 low | int32 close | float32 amount | int32 volume | int32 reserved``
    日期编码：``yyyymmdd``，价格单位为分（除以 100 还原）。
* ``.lc5``  5 分钟 K
    ``uint16 date_enc | uint16 time_enc | float32 open | float32 high | float32 low | float32 close | float32 amount | int32 volume | int32 reserved``
    日期编码：``date_enc = ((year - 2004) << 11) | (month * 100 + day)``，时间编码：``hour * 60 + minute``。
"""
from __future__ import annotations

import logging
import os
import struct
from datetime import datetime
from decimal import Decimal
from typing import Iterator

from iquant_domain.market import KlinePeriod, MarketBar

logger = logging.getLogger(__name__)

RECORD_SIZE = 32
_DAY_HEAD = struct.Struct("<iiiii")
_DAY_TAIL = struct.Struct("<fii")
_LC5_FMT = struct.Struct("<HHfffffii")


def get_record_count(file_path: str) -> int:
    try:
        return os.path.getsize(file_path) // RECORD_SIZE
    except OSError:
        return 0


def parse_day_file(
    file_path: str,
    *,
    full_code: str,
    record_offset: int = 0,
) -> Iterator[MarketBar]:
    """流式解析 .day 文件。

    参数：
        record_offset: 从第几条记录开始解析（用于增量导入时跳过已导入部分）
    """
    try:
        with open(file_path, "rb") as f:
            if record_offset > 0:
                f.seek(record_offset * RECORD_SIZE)
            buf = f.read()
    except OSError as exc:
        logger.error("tdx_day_read_failed", extra={"file": file_path, "error": str(exc)})
        return

    n = len(buf) // RECORD_SIZE
    for i in range(n):
        off = i * RECORD_SIZE
        date_int, raw_open, raw_high, raw_low, raw_close = _DAY_HEAD.unpack_from(buf, off)
        amount_f, volume, _ = _DAY_TAIL.unpack_from(buf, off + 20)
        year = date_int // 10000
        month = (date_int % 10000) // 100
        day = date_int % 100
        if not (1990 <= year <= 2099 and 1 <= month <= 12 and 1 <= day <= 31):
            continue
        try:
            bar_time = datetime(year, month, day)
        except ValueError:
            continue
        yield MarketBar(
            full_code=full_code,
            period=KlinePeriod.DAY,
            bar_time=bar_time,
            open=Decimal(raw_open) / Decimal(100),
            high=Decimal(raw_high) / Decimal(100),
            low=Decimal(raw_low) / Decimal(100),
            close=Decimal(raw_close) / Decimal(100),
            volume=int(volume),
            amount=Decimal(str(round(float(amount_f), 2))),
        )


def parse_lc5_file(
    file_path: str,
    *,
    full_code: str,
    record_offset: int = 0,
) -> Iterator[MarketBar]:
    """流式解析 .lc5 文件（5 分钟 K）。"""
    try:
        with open(file_path, "rb") as f:
            if record_offset > 0:
                f.seek(record_offset * RECORD_SIZE)
            buf = f.read()
    except OSError as exc:
        logger.error("tdx_lc5_read_failed", extra={"file": file_path, "error": str(exc)})
        return

    n = len(buf) // RECORD_SIZE
    for i in range(n):
        off = i * RECORD_SIZE
        (
            date_enc,
            time_enc,
            raw_open,
            raw_high,
            raw_low,
            raw_close,
            amount_f,
            volume,
            _reserved,
        ) = _LC5_FMT.unpack_from(buf, off)
        year = (date_enc >> 11) + 2004
        month = (date_enc % 2048) // 100
        day = (date_enc % 2048) % 100
        hour = time_enc // 60
        minute = time_enc % 60
        if not (2000 <= year <= 2099 and 1 <= month <= 12 and 1 <= day <= 31):
            continue
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            continue
        try:
            bar_time = datetime(year, month, day, hour, minute)
        except ValueError:
            continue
        yield MarketBar(
            full_code=full_code,
            period=KlinePeriod.MIN_5,
            bar_time=bar_time,
            open=Decimal(str(round(float(raw_open), 3))),
            high=Decimal(str(round(float(raw_high), 3))),
            low=Decimal(str(round(float(raw_low), 3))),
            close=Decimal(str(round(float(raw_close), 3))),
            volume=int(volume),
            amount=Decimal(str(round(float(amount_f), 2))),
        )
