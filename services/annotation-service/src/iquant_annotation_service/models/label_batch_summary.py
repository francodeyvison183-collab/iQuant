"""批次总结 ORM。"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base import PgBase


class LabelBatchSummaryORM(PgBase):
    __tablename__ = "label_batch_summary"

    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("label_batch.id", ondelete="CASCADE"),
        primary_key=True,
    )
    stats_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    profile_draft: Mapped[str] = mapped_column(Text, nullable=False, default="")
    insights_json: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    correction_options_json: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    user_corrections_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
