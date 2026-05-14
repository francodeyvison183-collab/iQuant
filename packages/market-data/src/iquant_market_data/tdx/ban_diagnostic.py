"""TDX 封禁/熔断时输出的聚合诊断日志（对齐 HQScanner ``_log_ban_diagnostic`` 思路）。"""
from __future__ import annotations

import json
import logging
import time
from collections import deque
from threading import Lock

logger = logging.getLogger(__name__)

_stats_lock = Lock()
_stats: dict[str, object] = {
    "total_requests": 0,
    "empty_responses": 0,
    "exceptions": 0,
    "host_requests": {},  # type: ignore[dict-item]
    "host_failures": {},  # type: ignore[dict-item]
    "recent_failures": deque(maxlen=20),  # (ts, code, host_key, exc_cls, msg)
    "started_at": time.time(),
}


def record_request(host_key: tuple[str, int]) -> None:
    with _stats_lock:
        _stats["total_requests"] = int(_stats["total_requests"]) + 1  # type: ignore[arg-type]
        hr: dict[tuple[str, int], int] = _stats["host_requests"]  # type: ignore[assignment]
        hr[host_key] = hr.get(host_key, 0) + 1


def record_failure(
    *,
    code: str,
    host_key: tuple[str, int],
    exc_cls: str,
    msg: str,
    is_empty: bool,
) -> None:
    with _stats_lock:
        if is_empty:
            _stats["empty_responses"] = int(_stats["empty_responses"]) + 1  # type: ignore[arg-type]
        else:
            _stats["exceptions"] = int(_stats["exceptions"]) + 1  # type: ignore[arg-type]
        hf: dict[tuple[str, int], int] = _stats["host_failures"]  # type: ignore[assignment]
        hf[host_key] = hf.get(host_key, 0) + 1
        rf: deque[tuple[float, str, tuple[str, int], str, str]] = _stats["recent_failures"]  # type: ignore[assignment]
        rf.append((time.time(), code, host_key, exc_cls, msg[:200]))


def log_ban_diagnostic(reason: str, *, extra: dict[str, object] | None = None) -> None:
    with _stats_lock:
        uptime = int(time.time() - float(_stats["started_at"]))  # type: ignore[arg-type]
        total = int(_stats["total_requests"])  # type: ignore[arg-type]
        empty = int(_stats["empty_responses"])  # type: ignore[arg-type]
        exc = int(_stats["exceptions"])  # type: ignore[arg-type]
        hr: dict[tuple[str, int], int] = _stats["host_requests"]  # type: ignore[assignment]
        hf: dict[tuple[str, int], int] = _stats["host_failures"]  # type: ignore[assignment]
        host_req = sorted(hr.items(), key=lambda kv: -kv[1])[:10]
        host_fail = sorted(hf.items(), key=lambda kv: -kv[1])[:10]
        recent = list(_stats["recent_failures"])[-10:]  # type: ignore[arg-type]

    extra_str = ""
    if extra:
        try:
            extra_str = " | extra=" + json.dumps(extra, ensure_ascii=False, default=str)
        except Exception:
            extra_str = f" | extra={extra!r}"

    host_req_str = ", ".join(f"{h[0]}:{h[1]}={n}" for h, n in host_req) or "-"
    host_fail_str = ", ".join(f"{h[0]}:{h[1]}={n}" for h, n in host_fail) or "-"
    recent_lines: list[str] = []
    for ts, code, host, exc_cls, msg in recent:
        recent_lines.append(
            f"    [{time.strftime('%H:%M:%S', time.localtime(ts))}] "
            f"code={code} host={host[0]}:{host[1]} exc={exc_cls} msg={msg}"
        )
    recent_block = "\n".join(recent_lines) if recent_lines else "    (无)"

    logger.error(  # noqa: G004 - 故意单行多行聚合，便于日志系统检索
        "[TDX-BAN-DIAG] 触发原因=%s 运行时长=%ss%s\n"
        "  总请求=%s 空响应=%s (%s%%) 异常=%s\n"
        "  主站请求分布 TOP10: %s\n"
        "  主站失败分布 TOP10: %s\n"
        "  最近失败:\n%s",
        reason,
        uptime,
        extra_str,
        total,
        empty,
        empty * 100 // max(total, 1),
        exc,
        host_req_str,
        host_fail_str,
        recent_block,
    )
