"""跨轮一致性报告 ORM。"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base import PgBase


class BlindConsistencyReportORM(PgBase):
    __tablename__ = "blind_consistency_report"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    admin_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    period: Mapped[str] = mapped_column(String(16), nullable=False, default="day")
    session_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scores_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    profile_draft: Mapped[str] = mapped_column(Text, nullable=False, default="")
    insights_json: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    correction_options_json: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    user_corrections_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    ready_for_strategy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
