"""TDX 代码工具函数测试。"""
from __future__ import annotations

import pytest

from iquant_domain.market import Market
from iquant_market_data.tdx.codes import (
    is_supported_code,
    market_to_tdx_id,
    split_full_code,
)


def test_split_full_code_ok():
    market, code = split_full_code("sh600519")
    assert market == Market.SH
    assert code == "600519"


@pytest.mark.parametrize("invalid", ["", "sh6005", "xx600519", "sh60051A"])
def test_split_full_code_invalid(invalid):
    with pytest.raises(ValueError):
        split_full_code(invalid)


def test_market_id_mapping():
    assert market_to_tdx_id(Market.SZ) == 0
    assert market_to_tdx_id(Market.SH) == 1
    assert market_to_tdx_id(Market.BJ) == 2


@pytest.mark.parametrize(
    "market,code,ok",
    [
        (Market.SH, "600519", True),
        (Market.SH, "688981", True),
        (Market.SZ, "000001", True),
        (Market.SZ, "300750", True),
        (Market.BJ, "830799", True),
        (Market.SH, "000001", False),
        (Market.SZ, "600519", False),
    ],
)
def test_is_supported_code(market, code, ok):
    assert is_supported_code(market, code) is ok
