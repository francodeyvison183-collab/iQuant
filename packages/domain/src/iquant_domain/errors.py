"""跨模块复用的错误类型。

层级：
    IquantError
        ├─ ValidationError      # 输入或 Schema 校验失败
        ├─ NotFoundError        # 资源不存在
        └─ MarketDataError      # 行情数据相关错误
                ├─ TdxProtocolError     # TDX 协议错误
                ├─ TdxHostUnavailable   # 所有主站都不可用
                └─ TdxGlobalCooldown    # 池级全局限速/冷却窗口内
"""
from __future__ import annotations


class IquantError(Exception):
    """iQuant 业务错误基类。所有业务异常必须继承自此类，便于上层捕获分类。"""

    code: str = "INTERNAL_ERROR"

    def __init__(self, message: str = "", *, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code
        self.message = message or self.code


class ValidationError(IquantError):
    code = "VALIDATION_ERROR"


class NotFoundError(IquantError):
    code = "RESOURCE_NOT_FOUND"


class MarketDataError(IquantError):
    code = "MARKET_DATA_ERROR"


class TdxProtocolError(MarketDataError):
    code = "TDX_PROTOCOL_ERROR"


class TdxHostUnavailable(MarketDataError):
    code = "TDX_HOST_UNAVAILABLE"


class TdxGlobalCooldown(MarketDataError):
    """TDX 全局限速/封禁保护：冷却窗口内禁止新建连接，避免 IP 被协同拉黑。

    与 HQScanner ``_PYTDX_KLINE_GLOBAL_COOLDOWN_UNTIL`` 语义对齐，供批次任务与连接池协同。
    """

    code = "TDX_GLOBAL_COOLDOWN"
