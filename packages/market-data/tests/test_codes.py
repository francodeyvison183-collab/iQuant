"""TDX 代码工具函数测试。"""
from __future__ import annotations

import pytest

from iquant_domain.market import Market
from iquant_market_data.tdx.codes import (
    is_a_share_stock_code,
    is_in_virtual_markets,
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
        (Market.SH, "000001", True),  # 上证指数
        (Market.SZ, "000001", True),
        (Market.SZ, "300750", True),
        (Market.SZ, "399001", True),  # 深证成指
        (Market.BJ, "830799", True),
        (Market.SZ, "600519", False),
    ],
)
def test_is_supported_code(market, code, ok):
    assert is_supported_code(market, code) is ok


@pytest.mark.parametrize(
    "market,code,ok",
    [
        (Market.SH, "600519", True),
        (Market.SH, "688981", True),
        (Market.SH, "000001", False),
        (Market.SZ, "000001", True),
        (Market.SZ, "300750", True),
        (Market.SZ, "399001", False),
        (Market.BJ, "830799", True),
    ],
)
def test_is_a_share_stock_code(market, code, ok):
    assert is_a_share_stock_code(market, code) is ok


class TestIsInVirtualMarkets:
    """is_in_virtual_markets 虚拟市场过滤测试。"""

    def test_none_markets_passes_all(self):
        assert is_in_virtual_markets("sh600519", None) is True
        assert is_in_virtual_markets("sz300750", None) is True

    def test_empty_markets_passes_all(self):
        assert is_in_virtual_markets("sh600519", []) is True

    @pytest.mark.parametrize(
        "full_code,expected",
        [
            ("sz300750", True),   # 创业板 300
            ("sz301258", True),   # 创业板 301
            ("sz000001", False),  # 深圳主板
            ("sh600519", False),  # 上海主板
            ("sh688981", False),  # 科创板
        ],
    )
    def test_cyb_filter(self, full_code, expected):
        assert is_in_virtual_markets(full_code, ["cyb"]) is expected

    @pytest.mark.parametrize(
        "full_code,expected",
        [
            ("sh688981", True),   # 科创板 688
            ("sh600519", False),  # 上海主板
            ("sz300750", False),  # 创业板
            ("sz000001", False),  # 深圳主板
        ],
    )
    def test_kcb_filter(self, full_code, expected):
        assert is_in_virtual_markets(full_code, ["kcb"]) is expected

    def test_sh_excludes_kcb(self):
        assert is_in_virtual_markets("sh600519", ["sh"]) is True
        assert is_in_virtual_markets("sh688981", ["sh"]) is False

    def test_sz_excludes_cyb(self):
        assert is_in_virtual_markets("sz000001", ["sz"]) is True
        assert is_in_virtual_markets("sz300750", ["sz"]) is False

    def test_bj_filter(self):
        assert is_in_virtual_markets("bj830799", ["bj"]) is True
        assert is_in_virtual_markets("sh600519", ["bj"]) is False

    def test_combined_markets(self):
        markets = ["cyb", "kcb"]
        assert is_in_virtual_markets("sz300750", markets) is True
        assert is_in_virtual_markets("sh688981", markets) is True
        assert is_in_virtual_markets("sh600519", markets) is False
        assert is_in_virtual_markets("sz000001", markets) is False

    def test_all_markets(self):
        markets = ["sh", "sz", "cyb", "kcb", "bj"]
        assert is_in_virtual_markets("sh600519", markets) is True
        assert is_in_virtual_markets("sh688981", markets) is True
        assert is_in_virtual_markets("sz000001", markets) is True
        assert is_in_virtual_markets("sz300750", markets) is True
        assert is_in_virtual_markets("bj830799", markets) is True

    def test_short_code_rejected(self):
        assert is_in_virtual_markets("sh6005", ["sh"]) is False
