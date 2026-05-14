"""行情领域模型。

所有跨模块传递的行情数据必须使用本文件定义的模型，禁止直接传递裸 dict 或 ORM 对象。
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Market(StrEnum):
    """市场枚举。"""

    SH = "sh"  # 上海
    SZ = "sz"  # 深圳
    BJ = "bj"  # 北交所


class KlinePeriod(StrEnum):
    """K 线周期。

    与 TDX category 的对应在 packages/market-data 中映射，此处只暴露语义。
    """

    MIN_1 = "1m"
    MIN_5 = "5m"
    MIN_15 = "15m"
    MIN_30 = "30m"
    MIN_60 = "60m"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"

    @property
    def is_intraday(self) -> bool:
        return self in {
            KlinePeriod.MIN_1,
            KlinePeriod.MIN_5,
            KlinePeriod.MIN_15,
            KlinePeriod.MIN_30,
            KlinePeriod.MIN_60,
        }


class Symbol(BaseModel):
    """标的基础信息。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=6, max_length=6, description="纯 6 位数字代码，如 600519")
    market: Market = Field(description="市场")
    name: str = Field(min_length=1, max_length=64, description="标的名称")
    asset_type: str = Field(default="stock", description="stock / etf / index")
    list_date: date | None = None
    delist_date: date | None = None

    @property
    def full_code(self) -> str:
        """带市场前缀的完整代码，如 sh600519。"""
        return f"{self.market.value}{self.code}"

    @field_validator("code")
    @classmethod
    def _code_is_digits(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("code 必须是 6 位数字")
        return v


class MarketBar(BaseModel):
    """单根 K 线。

    所有价格字段使用 Decimal，避免浮点累计误差。
    成交量为整数（股或手），成交额为元。
    """

    model_config = ConfigDict(extra="forbid")

    full_code: str = Field(description="带前缀的完整代码，如 sh600519")
    period: KlinePeriod
    bar_time: datetime = Field(description="K 线时间（intraday 取该 bar 的结束时间，日线取交易日 0 点）")
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int = Field(ge=0, description="成交量（股或手，由数据源决定）")
    amount: Decimal = Field(ge=0, description="成交额（元）")
    adj_factor: Decimal | None = Field(default=None, description="复权因子，None 表示未复权")

    @model_validator(mode="after")
    def _check_ohlc_consistency(self) -> "MarketBar":
        if self.high < self.low:
            raise ValueError(f"high={self.high} < low={self.low}")
        if self.high < self.open or self.high < self.close:
            raise ValueError(
                f"high={self.high} 必须 >= open={self.open} 和 close={self.close}"
            )
        if self.low > self.open or self.low > self.close:
            raise ValueError(
                f"low={self.low} 必须 <= open={self.open} 和 close={self.close}"
            )
        return self


class MarketBarBatch(BaseModel):
    """一批同标的同周期的 K 线，便于批量写入与传递。"""

    model_config = ConfigDict(extra="forbid")

    full_code: str
    period: KlinePeriod
    bars: list[MarketBar]

    def __len__(self) -> int:
        return len(self.bars)

    @property
    def is_empty(self) -> bool:
        return not self.bars
