"""盲测操作 ORM。"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import PgBase

if TYPE_CHECKING:
    from .blind_session import BlindSessionORM


class BlindActionORM(PgBase):
    __tablename__ = "blind_action"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("blind_session.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bar_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period: Mapped[str] = mapped_column(String(16), nullable=False, default="day")
    user_action: Mapped[str] = mapped_column(String(16), nullable=False)
    features_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    strategy_signal: Mapped[str | None] = mapped_column(String(16), nullable=True)
    user_reasons: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped["BlindSessionORM"] = relationship("BlindSessionORM", back_populates="actions")
