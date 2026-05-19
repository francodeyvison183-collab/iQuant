"""单笔买卖标注 ORM。"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from typing import TYPE_CHECKING

from .base import PgBase

if TYPE_CHECKING:
    from .label_session import LabelSessionORM


class LabelPairORM(PgBase):
    __tablename__ = "label_pair"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("label_session.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    buy_bar_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sell_bar_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    buy_close: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    sell_close: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    return_pct: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)

    session: Mapped["LabelSessionORM"] = relationship("LabelSessionORM", back_populates="pairs")
