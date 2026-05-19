"""盲测会话 ORM。"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import PgBase

if TYPE_CHECKING:
    from .blind_action import BlindActionORM


class BlindSessionORM(PgBase):
    __tablename__ = "blind_session"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # 库级 FK 见 Alembic 0006；ORM 不声明跨服务表 FK
    admin_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    full_code: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(16), nullable=False, default="day")
    range_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    range_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cursor_bar_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cursor_period: Mapped[str] = mapped_column(String(16), nullable=False, default="day")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    strategy_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="blind_replay")
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    cash_balance: Mapped[Decimal] = mapped_column(
        Numeric(20, 4), nullable=False, default=Decimal("1000000")
    )
    position_qty: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), nullable=False, default=Decimal("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    actions: Mapped[list["BlindActionORM"]] = relationship(
        "BlindActionORM",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="BlindActionORM.bar_time",
    )
