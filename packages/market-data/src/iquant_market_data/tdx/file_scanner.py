"""扫描本地通达信 vipdoc 目录。

通达信安装目录中行情文件分布：

::

    vipdoc/
        sh/lday/sh600519.day      # 日 K（32 字节定长）
        sh/fzline/sh600519.lc5    # 5 分钟 K（32 字节定长）
        sz/lday/sz000001.day
        ...

本模块只负责"找到文件 + 标注 (market, code, period)"，解析交给 :mod:`file_parser`。
"""
from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass

from iquant_domain.market import KlinePeriod, Market

from .codes import is_supported_code

logger = logging.getLogger(__name__)

# vipdoc 子目录 -> (period, 扩展名)
SUBDIR_MAP: dict[str, tuple[KlinePeriod, str]] = {
    "lday": (KlinePeriod.DAY, ".day"),
    "fzline": (KlinePeriod.MIN_5, ".lc5"),
    "minline": (KlinePeriod.MIN_1, ".lc1"),
}


@dataclass(slots=True)
class TdxFileInfo:
    """扫描到的单个 K 线文件元信息。"""

    file_path: str
    market: Market
    code: str
    full_code: str
    period: KlinePeriod
    file_size: int
    file_mtime: float

    @property
    def signature(self) -> tuple[int, float]:
        """用于判断文件是否变化的二元组。"""
        return (self.file_size, self.file_mtime)


def scan_tdx_files(root_dir: str, *, periods: list[KlinePeriod] | None = None) -> list[TdxFileInfo]:
    """扫描整个 vipdoc 目录。

    参数：
        root_dir: vipdoc 根目录的绝对路径
        periods: 只扫这些周期；None 表示扫描全部已实现的周期（day + 5m + 1m）
    """
    if not root_dir or not os.path.isdir(root_dir):
        logger.warning("tdx_vipdoc_missing", extra={"root_dir": root_dir})
        return []

    allow_periods: set[KlinePeriod] | None = set(periods) if periods else None
    out: list[TdxFileInfo] = []

    for market in Market:
        for subdir, (period, ext) in SUBDIR_MAP.items():
            if allow_periods is not None and period not in allow_periods:
                continue
            dir_path = os.path.join(root_dir, market.value, subdir)
            if not os.path.isdir(dir_path):
                continue
            try:
                with os.scandir(dir_path) as it:
                    entries = list(it)
            except OSError as exc:
                logger.warning("tdx_scan_dir_failed", extra={"dir": dir_path, "error": str(exc)})
                continue

            for entry in entries:
                if not entry.is_file() or not entry.name.lower().endswith(ext):
                    continue
                raw = entry.name.split(".")[0].lower()
                if raw.startswith(market.value):
                    code = raw[len(market.value) :]
                elif raw.startswith(("sh", "sz", "bj")):
                    code = raw[2:]
                else:
                    code = raw
                if not is_supported_code(market, code):
                    continue
                try:
                    stat = entry.stat(follow_symlinks=False)
                except OSError:
                    continue
                out.append(
                    TdxFileInfo(
                        file_path=entry.path,
                        market=market,
                        code=code,
                        full_code=f"{market.value}{code}",
                        period=period,
                        file_size=stat.st_size,
                        file_mtime=stat.st_mtime,
                    )
                )

    logger.info("tdx_scan_done", extra={"root_dir": root_dir, "files": len(out)})
    return out


def scan_changed_files(
    root_dir: str,
    *,
    state_map: Mapping[str, tuple[int, float]],
    periods: list[KlinePeriod] | None = None,
) -> tuple[list[TdxFileInfo], list[TdxFileInfo]]:
    """与上次导入状态对比，区分变更/未变文件。

    参数：
        state_map: ``{file_path: (file_size, file_mtime)}``
    返回：
        (changed, unchanged)
    """
    all_files = scan_tdx_files(root_dir, periods=periods)
    changed: list[TdxFileInfo] = []
    unchanged: list[TdxFileInfo] = []
    for fi in all_files:
        prev = state_map.get(fi.file_path)
        if prev is None or prev != fi.signature:
            changed.append(fi)
        else:
            unchanged.append(fi)
    return changed, unchanged
