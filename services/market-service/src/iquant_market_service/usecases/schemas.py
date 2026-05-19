"""用例的输入/输出 schema（与 HTTP schema 解耦）。"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from iquant_domain.market import KlinePeriod


class ScanPreviewResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    data_dir: str
    total_files: int
    by_period: dict[str, int]
    by_market: dict[str, dict[str, int]]
    changed_files: int
    unchanged_files: int


class ImportTaskRef(BaseModel):
    """提交任务后给调用方的句柄。"""

    model_config = ConfigDict(frozen=True)

    task_id: str
    status: str


class BrowserSymbolRow(BaseModel):
    """数据浏览左侧标的行。"""

    model_config = ConfigDict(frozen=True)

    full_code: str
    code: str
    market: str
    name: str
    asset_type: str = "stock"


class BarPoint(BaseModel):
    """API 友好的 K 线点。"""

    model_config = ConfigDict(frozen=True)

    bar_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    amount: Decimal


class BarQueryResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    full_code: str
    period: KlinePeriod
    bars: list[BarPoint]


class SymbolCoverage(BaseModel):
    """单标的某周期的覆盖情况。"""

    model_config = ConfigDict(frozen=True)

    full_code: str
    period: KlinePeriod
    first_bar_time: datetime | None
    last_bar_time: datetime | None
    bar_count: int
