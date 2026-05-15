"""TDX 协议常量与代码工具。"""
from __future__ import annotations

import re

from iquant_domain.market import KlinePeriod, Market

# ── TDX K 线 category 常量（参考 pytdx）────────────────────────────────────────
TDX_CATEGORY_MIN_5 = 0
TDX_CATEGORY_MIN_15 = 1
TDX_CATEGORY_MIN_30 = 2
TDX_CATEGORY_MIN_60 = 3
TDX_CATEGORY_DAY = 9
TDX_CATEGORY_WEEK = 5
TDX_CATEGORY_MONTH = 6
TDX_CATEGORY_MIN_1 = 8

PERIOD_TO_CATEGORY: dict[KlinePeriod, int] = {
    KlinePeriod.MIN_1: TDX_CATEGORY_MIN_1,
    KlinePeriod.MIN_5: TDX_CATEGORY_MIN_5,
    KlinePeriod.MIN_15: TDX_CATEGORY_MIN_15,
    KlinePeriod.MIN_30: TDX_CATEGORY_MIN_30,
    KlinePeriod.MIN_60: TDX_CATEGORY_MIN_60,
    KlinePeriod.DAY: TDX_CATEGORY_DAY,
    KlinePeriod.WEEK: TDX_CATEGORY_WEEK,
    KlinePeriod.MONTH: TDX_CATEGORY_MONTH,
}

# ── A 股代码规则 ──────────────────────────────────────────────────────────────
CODE_PATTERNS: dict[Market, re.Pattern[str]] = {
    Market.SH: re.compile(r"^(000|600|601|603|605|688)\d{3}$"),
    Market.SZ: re.compile(r"^(000|001|002|003|300|301|399)\d{3}$"),
    Market.BJ: re.compile(r"^(43|83|87|88|92)\d{4}$"),
}


def market_to_tdx_id(market: Market) -> int:
    """TDX 协议中市场 ID：0=SZ, 1=SH, 2=BJ。"""
    return {Market.SZ: 0, Market.SH: 1, Market.BJ: 2}[market]


def split_full_code(full_code: str) -> tuple[Market, str]:
    """解析 ``sh600519`` -> (Market.SH, "600519")。"""
    fc = full_code.strip().lower()
    if len(fc) < 8 or fc[:2] not in ("sh", "sz", "bj"):
        raise ValueError(f"非法 full_code: {full_code!r}")
    market = Market(fc[:2])
    code = fc[2:].split(".")[0]
    if not code.isdigit() or len(code) != 6:
        raise ValueError(f"非法 6 位代码: {full_code!r}")
    return market, code


def is_supported_code(market: Market, code: str) -> bool:
    """判断该市场是否支持该代码。用于过滤 vipdoc 目录里 ETF、指数等无关文件。"""
    pattern = CODE_PATTERNS.get(market)
    return bool(pattern and pattern.match(code))


def is_a_share_stock_code(market: Market, code: str) -> bool:
    """A 股股票代码前缀过滤（深/沪/北交所常见股票段）。"""
    if len(code) != 6 or not code.isdigit():
        return False
    if market == Market.SZ:
        return code[:2] in ("00", "30", "20")
    if market == Market.SH:
        return code[:2] in ("60", "68")
    if market == Market.BJ:
        return code[0] in ("4", "8", "9")
    return False


def is_in_virtual_markets(full_code: str, virtual_markets: list[str] | None) -> bool:
    """判断代码是否属于指定的虚拟市场集合（支持 cyb 创业板、kcb 科创板）。"""
    if not virtual_markets:
        return True
        
    fc = full_code.lower()
    if len(fc) < 8:
        return False
        
    market_prefix = fc[:2]
    code = fc[2:]
    
    if "cyb" in virtual_markets and market_prefix == "sz" and (code.startswith("300") or code.startswith("301")):
        return True
    if "kcb" in virtual_markets and market_prefix == "sh" and code.startswith("688"):
        return True
    if "sz" in virtual_markets and market_prefix == "sz" and not (code.startswith("300") or code.startswith("301")):
        return True
    if "sh" in virtual_markets and market_prefix == "sh" and not code.startswith("688"):
        return True
    if "bj" in virtual_markets and market_prefix == "bj":
        return True
        
    return False
