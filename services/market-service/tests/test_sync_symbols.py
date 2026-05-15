"""标的名称清洗与同步逻辑单测。"""
from __future__ import annotations

from iquant_market_service.usecases.sync_symbols import sanitize_stock_name


def test_sanitize_stock_name_keeps_chinese() -> None:
    assert sanitize_stock_name("贵州茅台", "sh600519") == "贵州茅台"


def test_sanitize_stock_name_fallback_on_empty() -> None:
    assert sanitize_stock_name("", "sh600519") == "600519"
    assert sanitize_stock_name("sh600519", "sh600519") == "600519"


def test_sanitize_stock_name_fallback_on_ascii_garbage() -> None:
    assert sanitize_stock_name("STOCK", "sz000001") == "000001"
