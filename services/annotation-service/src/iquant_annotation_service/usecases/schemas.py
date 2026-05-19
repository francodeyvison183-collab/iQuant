"""标注 API 用 Pydantic 模型。"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LabelPairIn(BaseModel):
    model_config = ConfigDict(frozen=True)

    buy_bar_time: datetime
    sell_bar_time: datetime
    buy_close: Annotated[Decimal, Field(gt=Decimal("0"), max_digits=20, decimal_places=6)]
    sell_close: Annotated[Decimal, Field(max_digits=20, decimal_places=6)]


class LabelSessionCreateIn(BaseModel):
    model_config = ConfigDict(frozen=True)

    full_code: str = Field(min_length=4, max_length=24)
    period: str = Field(default="day", max_length=16)
    title: str | None = Field(default=None, max_length=128)


class LabelPairOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    sort_order: int
    buy_bar_time: datetime
    sell_bar_time: datetime
    buy_close: str
    sell_close: str
    return_pct: str


class LabelSessionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    full_code: str
    period: str
    title: str | None
    created_at: datetime
    updated_at: datetime
    pairs: list[LabelPairOut]


class LabelSessionSummaryOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    full_code: str
    period: str
    title: str | None
    created_at: datetime
    pair_count: int


class LabelBatchCreateIn(BaseModel):
    model_config = ConfigDict(frozen=True)

    period: str = Field(default="day", max_length=16)
    market: str | None = Field(default=None, max_length=16)
    batch_size: int = Field(default=20, ge=1, le=50)


class LabelQueueItemOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    sort_order: int
    full_code: str
    symbol_name: str
    status: str
    skip_reason: str | None
    session_id: UUID | None
    pair_count: int = 0


class LabelBatchProgressOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    total: int
    completed: int
    skipped: int
    pending: int
    current_index: int | None


class LabelBatchOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    period: str
    market_filter: str | None
    batch_size: int
    status: str
    created_at: datetime
    completed_at: datetime | None
    progress: LabelBatchProgressOut
    items: list[LabelQueueItemOut]


class LabelBatchCurrentOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    batch: LabelBatchOut
    current_item: LabelQueueItemOut | None
    session: LabelSessionOut | None
    done: bool


class LabelBatchSummaryOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    batch_id: UUID
    stats: dict[str, object]
    profile_draft: str
    insights: list[str]
    correction_options: list[dict[str, str]]
    user_corrections: list[str]
    outlier_pairs: list[dict[str, str]]
    created_at: datetime
    updated_at: datetime


class LabelBatchSummaryPatchIn(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_corrections: list[str] = Field(default_factory=list)


class LabelBatchListItemOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    period: str
    market_filter: str | None
    batch_size: int
    status: str
    created_at: datetime
    completed_at: datetime | None
    completed_count: int
    skipped_count: int
    pair_count: int
    profile_draft: str | None
