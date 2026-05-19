"""行为策略 ORM。"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import PgBase

if TYPE_CHECKING:
    from .behavior_strategy_version import BehaviorStrategyVersionORM


class BehaviorStrategyORM(PgBase):
    __tablename__ = "behavior_strategy"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    admin_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="blind_replay")
    consistency_report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    period: Mapped[str] = mapped_column(String(16), nullable=False, default="day")
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    versions: Mapped[list["BehaviorStrategyVersionORM"]] = relationship(
        "BehaviorStrategyVersionORM",
        back_populates="strategy",
        cascade="all, delete-orphan",
        order_by="BehaviorStrategyVersionORM.version_no",
    )
