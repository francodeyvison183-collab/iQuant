"""扫描本地 vipdoc 目录预览。"""
from __future__ import annotations

import os
from collections import defaultdict

from iquant_market_data.tdx.file_scanner import scan_tdx_files

from ..config import get_market_settings
from ..db import pg_session
from ..repositories.import_task_repo import ImportStateRepo
from .schemas import ScanPreviewResult


async def scan_local_preview(*, vipdoc_dir: str | None = None, markets: list[str] | None = None) -> ScanPreviewResult:
    """预览本地 TDX 文件扫描结果，不写入任何数据。"""
    s = get_market_settings()
    data_dir = (vipdoc_dir or s.tdx_vipdoc_dir).strip()
    if not data_dir or not os.path.isdir(data_dir):
        return ScanPreviewResult(
            data_dir=data_dir,
            total_files=0,
            by_period={},
            by_market={},
            changed_files=0,
            unchanged_files=0,
        )

    files = scan_tdx_files(data_dir, markets=markets)
    by_period: dict[str, int] = defaultdict(int)
    by_market: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for f in files:
        by_period[f.period.value] += 1
        by_market[f.market.value][f.period.value] += 1

    async with pg_session() as ses:
        state_map = await ImportStateRepo(ses).load_state_map([f.file_path for f in files])

    changed = 0
    for f in files:
        prev = state_map.get(f.file_path)
        if prev is None or (prev[0], prev[1]) != f.signature:
            changed += 1
    unchanged = len(files) - changed

    return ScanPreviewResult(
        data_dir=data_dir,
        total_files=len(files),
        by_period=dict(by_period),
        by_market={m: dict(d) for m, d in by_market.items()},
        changed_files=changed,
        unchanged_files=unchanged,
    )
