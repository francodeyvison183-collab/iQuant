"""通达信在线行情客户端（基于 pytdx）。

同步阻塞 API，由 ``TdxConnectionPool.run_sync`` 在线程池中调用。
协议编解码、zlib 解压等由 pytdx 负责；本模块只做连接管理与领域模型转换。
"""
from __future__ import annotations

import logging
from datetime import datetime

from iquant_domain.errors import TdxProtocolError
from iquant_domain.market import KlinePeriod, MarketBar, MarketBarBatch
from pytdx.hq import TdxHq_API

from .bar_range_filter import filter_bars_in_date_range
from .codes import PERIOD_TO_CATEGORY, market_to_tdx_id, split_full_code
from .pytdx_convert import bars_from_pytdx

logger = logging.getLogger(__name__)

_TDX_PAGE_SIZE = 800


class TdxClient:
    """单条 pytdx 连接的薄封装，接口与历史自研客户端保持一致。"""

    def __init__(
        self,
        host: str,
        port: int,
        *,
        connect_timeout: float = 5.0,
        read_timeout: float = 10.0,
    ) -> None:
        self.host = host
        self.port = port
        self.connect_timeout = max(1, int(connect_timeout))
        self.read_timeout = max(1, int(read_timeout))
        self._api: TdxHq_API | None = None

    def connect(self) -> None:
        api = TdxHq_API(raise_exception=False)
        ok = api.connect(self.host, self.port, time_out=self.connect_timeout)
        if not ok:
            raise TdxProtocolError(f"TDX 连接失败 {self.host}:{self.port}")
        if api.client is not None:
            api.client.settimeout(self.read_timeout)
        self._api = api
        logger.info("tdx_connected", extra={"host": self.host, "port": self.port})

    def close(self) -> None:
        if self._api is not None:
            try:
                self._api.disconnect()
            except OSError:
                pass
            self._api = None

    @property
    def connected(self) -> bool:
        return self._api is not None and self._api.client is not None

    def __enter__(self) -> TdxClient:
        if not self.connected:
            self.connect()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _api_or_connect(self) -> TdxHq_API:
        if not self.connected:
            self.connect()
        assert self._api is not None
        return self._api

    def fetch_bars(
        self,
        *,
        full_code: str,
        period: KlinePeriod,
        offset: int = 0,
        count: int = 800,
    ) -> MarketBarBatch:
        """单次 ``get_security_bars``（offset 越大越旧）。"""
        if period not in PERIOD_TO_CATEGORY:
            raise TdxProtocolError(f"不支持的周期: {period}")
        market, code = split_full_code(full_code)
        category = PERIOD_TO_CATEGORY[period]
        api = self._api_or_connect()
        try:
            raw = api.get_security_bars(
                category,
                market_to_tdx_id(market),
                code,
                int(offset),
                min(int(count), _TDX_PAGE_SIZE),
            )
        except Exception as exc:  # noqa: BLE001
            self.close()
            raise TdxProtocolError(f"TDX K 线请求失败 {full_code}: {exc}") from exc
        bars = bars_from_pytdx(raw, full_code=full_code, period=period)
        return MarketBarBatch(full_code=full_code, period=period, bars=bars)

    def fetch_bars_paged(
        self,
        *,
        full_code: str,
        period: KlinePeriod,
        max_count: int = 8000,
        page_size: int = 800,
    ) -> MarketBarBatch:
        """分页拉取最近 ``max_count`` 根 K 线，按时间升序合并。"""
        page_size = min(page_size, _TDX_PAGE_SIZE)
        all_bars: list[MarketBar] = []
        offset = 0
        while len(all_bars) < max_count:
            batch = self.fetch_bars(
                full_code=full_code,
                period=period,
                offset=offset,
                count=min(page_size, max_count - len(all_bars)),
            )
            if batch.is_empty:
                break
            all_bars[0:0] = batch.bars
            offset += len(batch.bars)
            if len(batch.bars) < page_size:
                break
        return MarketBarBatch(full_code=full_code, period=period, bars=all_bars)

    def fetch_bars_in_range(
        self,
        *,
        full_code: str,
        period: KlinePeriod,
        start: datetime,
        end: datetime | None = None,
        page_size: int = 800,
        hard_max_bars: int = 20000,
    ) -> MarketBarBatch:
        """按时间区间往回翻页拉取（TDX 仅支持 offset/count）。"""
        page_size = min(page_size, _TDX_PAGE_SIZE)
        all_bars: list[MarketBar] = []
        offset = 0
        while len(all_bars) < hard_max_bars:
            batch = self.fetch_bars(
                full_code=full_code,
                period=period,
                offset=offset,
                count=page_size,
            )
            if batch.is_empty:
                break
            all_bars[0:0] = batch.bars
            oldest = batch.bars[0].bar_time
            if oldest <= start:
                break
            if len(batch.bars) < page_size:
                break
            offset += len(batch.bars)
        filtered = filter_bars_in_date_range(
            all_bars, period=period, start=start, end=end
        )
        return MarketBarBatch(full_code=full_code, period=period, bars=filtered)

    def fetch_security_count(self, market: int) -> int:
        api = self._api_or_connect()
        try:
            return int(api.get_security_count(market) or 0)
        except Exception as exc:  # noqa: BLE001
            self.close()
            raise TdxProtocolError(f"get_security_count 失败 market={market}: {exc}") from exc

    def fetch_security_list(self, market: int, start: int) -> list[tuple[str, str]]:
        api = self._api_or_connect()
        try:
            raw = api.get_security_list(market, start) or []
        except Exception as exc:  # noqa: BLE001
            self.close()
            raise TdxProtocolError(f"get_security_list 失败 market={market}: {exc}") from exc
        out: list[tuple[str, str]] = []
        for item in raw:
            code = str(item.get("code", "")).strip()
            name = str(item.get("name", "")).strip()
            if code:
                out.append((code, name))
        return out
