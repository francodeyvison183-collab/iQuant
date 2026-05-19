"""SSE 一次性 ticket。"""
from __future__ import annotations

from ..config import get_identity_settings
from ..redis_client import consume_sse_ticket, issue_sse_ticket
from .schemas import SseTicketResult


async def create_sse_ticket(*, admin_user_id: int, task_id: str) -> SseTicketResult:
    settings = get_identity_settings()
    ticket = await issue_sse_ticket(
        admin_user_id=admin_user_id,
        task_id=task_id,
        ttl_seconds=settings.sse_ticket_seconds,
    )
    return SseTicketResult(ticket=ticket, expires_in=settings.sse_ticket_seconds)


async def validate_sse_ticket(*, ticket: str, task_id: str) -> int:
    admin_id = await consume_sse_ticket(ticket, task_id=task_id)
    if admin_id is None:
        from iquant_domain.errors import AuthError

        raise AuthError("无效或已过期的 SSE ticket", code="AUTH_INVALID")
    return admin_id
