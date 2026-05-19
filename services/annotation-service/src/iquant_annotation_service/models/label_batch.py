"""标注批次 ORM。"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import PgBase


class LabelBatchORM(PgBase):
    __tablename__ = "label_batch"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    admin_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    period: Mapped[str] = mapped_column(String(16), nullable=False, default="day")
    market_filter: Mapped[str | None] = mapped_column(String(16), nullable=True)
    batch_size: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    items: Mapped[list["LabelQueueItemORM"]] = relationship(
        "LabelQueueItemORM",
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by="LabelQueueItemORM.sort_order",
    )
