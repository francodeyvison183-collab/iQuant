"""浏览器端错误上报，写入服务端 JSONL 日志文件。"""
from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from iquant_api.config import get_api_settings

router = APIRouter(tags=["client-errors"])


class ClientErrorIn(BaseModel):
    message: str = Field(..., max_length=8000)
    stack: str = Field(default="", max_length=48000)
    source: str = Field(default="", max_length=512)


def _append_jsonl(path: str, payload: dict[str, object]) -> None:
    raw = Path(path)
    p = raw if raw.is_absolute() else Path.cwd() / raw
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, ensure_ascii=False) + "\n"
    with p.open("a", encoding="utf-8") as f:
        f.write(line)


@router.post("/client-errors")
async def report_client_error(body: ClientErrorIn, request: Request) -> dict[str, bool]:
    """接收管理端 SPA 上报的运行时错误，追加写入 ``client_error_log_path``。"""
    settings = get_api_settings()
    payload: dict[str, object] = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "message": body.message,
        "stack": body.stack,
        "source": body.source,
        "referer": request.headers.get("referer", ""),
        "user_agent": (request.headers.get("user-agent") or "")[:512],
        "client_ip": request.client.host if request.client else "",
    }
    await asyncio.to_thread(_append_jsonl, settings.client_error_log_path, payload)
    return {"ok": True}
