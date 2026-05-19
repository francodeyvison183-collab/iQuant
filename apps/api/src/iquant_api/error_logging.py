"""为根 logger 挂载 ERROR 级别滚动文件，便于排查未捕获异常与任务失败。"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_attached_paths: set[str] = set()


def attach_error_log_file(path: str, *, max_bytes: int = 10_485_760, backup_count: int = 5) -> None:
    """向根 logger 追加一个仅接收 ERROR 及以上的 RotatingFileHandler（同一路径只挂一次）。"""
    raw = Path(path)
    resolved = str(raw.resolve()) if raw.is_absolute() else str((Path.cwd() / raw).resolve())
    if resolved in _attached_paths:
        return
    Path(resolved).parent.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    fmt = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    fh = RotatingFileHandler(
        resolved,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    fh.setLevel(logging.ERROR)
    fh.setFormatter(fmt)
    root.addHandler(fh)
    _attached_paths.add(resolved)
