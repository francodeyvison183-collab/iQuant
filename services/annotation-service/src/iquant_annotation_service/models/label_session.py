"""标注会话 ORM。"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import PgBase


class LabelSessionORM(PgBase):
    __tablename__ = "label_session"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # 库级 FK 见 Alembic 0003；ORM 不声明跨服务表 FK，避免独立 MetaData 无法解析 admin_user
    admin_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    full_code: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(16), nullable=False, default="day")
    title: Mapped[str | None] = mapped_column(String(128), nullable=True)
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

    pairs: Mapped[list["LabelPairORM"]] = relationship(
        "LabelPairORM",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="LabelPairORM.sort_order",
    )
