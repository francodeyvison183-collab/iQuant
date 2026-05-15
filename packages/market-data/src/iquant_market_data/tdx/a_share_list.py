"""从 TDX 拉取 A 股全市场代码（pytdx ``get_security_list``）。"""
from __future__ import annotations

import logging

from iquant_domain.market import Market

from .client import TdxClient
from .codes import is_a_share_stock_code

logger = logging.getLogger(__name__)

_TDX_MARKETS: tuple[tuple[int, Market], ...] = (
    (0, Market.SZ),
    (1, Market.SH),
    (2, Market.BJ),
)


def list_a_share_stocks(client: TdxClient) -> list[tuple[str, str]]:
    """返回 ``(full_code, stock_name)`` 列表。"""
    if not client.connected:
        client.connect()

    pairs: list[tuple[str, str]] = []
    for tdx_market, market in _TDX_MARKETS:
        try:
            security_count = client.fetch_security_count(tdx_market)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "tdx_security_count_failed",
                extra={"market": market.value, "error": str(exc)},
            )
            try:
                client.close()
                client.connect()
            except Exception:  # noqa: BLE001
                pass
            continue
        if security_count <= 0:
            continue

        for start in range(0, security_count, 1000):
            try:
                rows = client.fetch_security_list(tdx_market, start)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "tdx_security_list_failed",
                    extra={"market": market.value, "start": start, "error": str(exc)},
                )
                continue
            for code, name in rows:
                if not is_a_share_stock_code(market, code):
                    continue
                pairs.append((f"{market.value}{code}", name))

    seen: set[str] = set()
    uniq: list[tuple[str, str]] = []
    for fc, nm in pairs:
        if fc in seen:
            continue
        seen.add(fc)
        uniq.append((fc, nm))
    logger.info("tdx_a_share_list_done", extra={"count": len(uniq)})
    return uniq


def list_a_share_full_codes(client: TdxClient) -> list[str]:
    return [fc for fc, _ in list_a_share_stocks(client)]
