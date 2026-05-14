"""通达信行情 TCP 客户端。

注意：通达信行情协议是同步阻塞 TCP，本类保持同步实现，由上层在线程池中调用，
避免在 asyncio event loop 里直接阻塞。需要异步语义时请使用 ``TdxConnectionPool``。

参考实现：HQScanner.app.services.tdx_service / pytdx。
"""
from __future__ import annotations

import logging
import socket
import struct
from datetime import datetime
from decimal import Decimal
from typing import Iterable

from iquant_domain.errors import TdxProtocolError
from iquant_domain.market import KlinePeriod, MarketBar, MarketBarBatch

from .codes import (
    PERIOD_TO_CATEGORY,
    TDX_CATEGORY_DAY,
    TDX_CATEGORY_MONTH,
    TDX_CATEGORY_WEEK,
    market_to_tdx_id,
    split_full_code,
)

logger = logging.getLogger(__name__)

# TDX 协议握手包：服务端必须接受全部 3 个 setup 包后才会响应 K 线请求
_SETUP_CMDS_HEX: tuple[str, ...] = (
    "0c0218930001030003000d0001",
    "0c0218940001030003000d0002",
    "0c031899000120002000db0fd5d0c9ccd6a4a8af"
    "0000008fc22540130000d500c9ccbdf0d7ea00000002",
)


class TdxClient:
    """同步 TDX TCP 客户端。"""

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
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self._sock: socket.socket | None = None

    # ── 连接生命周期 ──────────────────────────────────────────────────────────

    def connect(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.connect_timeout)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        if hasattr(socket, "TCP_KEEPIDLE"):
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
        if hasattr(socket, "TCP_KEEPINTVL"):
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 15)
        if hasattr(socket, "TCP_KEEPCNT"):
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
        try:
            sock.connect((self.host, self.port))
            for cmd in _SETUP_CMDS_HEX:
                sock.sendall(bytes.fromhex(cmd))
                _ = sock.recv(1024)
        except (TimeoutError, OSError) as exc:
            try:
                sock.close()
            except OSError:
                pass
            raise TdxProtocolError(f"TDX 握手失败 {self.host}:{self.port} - {exc}") from exc
        sock.settimeout(self.read_timeout)
        self._sock = sock
        logger.info("tdx_connected", extra={"host": self.host, "port": self.port})

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            finally:
                self._sock = None

    @property
    def connected(self) -> bool:
        return self._sock is not None

    def __enter__(self) -> "TdxClient":
        if not self.connected:
            self.connect()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # ── 业务接口 ──────────────────────────────────────────────────────────────

    def fetch_bars(
        self,
        *,
        full_code: str,
        period: KlinePeriod,
        offset: int = 0,
        count: int = 800,
    ) -> MarketBarBatch:
        """单次请求拉取一段 K 线（最旧 → 最新）。

        TDX 单次请求最多约 800 根；获取更长历史需要分页（由 offset 控制）。
        """
        if period not in PERIOD_TO_CATEGORY:
            raise TdxProtocolError(f"不支持的周期: {period}")
        if not self.connected:
            self.connect()

        market, code = split_full_code(full_code)
        category = PERIOD_TO_CATEGORY[period]
        req = self._build_kline_request(market_to_tdx_id(market), code.encode("ascii"), category, offset, count)

        assert self._sock is not None
        try:
            self._sock.sendall(req)
            response = self._recv_response()
        except (BrokenPipeError, ConnectionResetError, OSError, TimeoutError) as exc:
            self.close()
            raise TdxProtocolError(f"TDX I/O 失败 {full_code}: {exc}") from exc

        bars = self._parse_kline_response(response, period=period, full_code=full_code)
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
        page_size = min(page_size, 800)
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
            all_bars[0:0] = batch.bars  # 旧批 prepend
            offset += len(batch.bars)
            if len(batch.bars) < page_size:
                break
        return MarketBarBatch(full_code=full_code, period=period, bars=all_bars)

    # ── 协议封装 ──────────────────────────────────────────────────────────────

    @staticmethod
    def _build_kline_request(
        market: int, code: bytes, category: int, start: int, count: int
    ) -> bytes:
        if len(code) != 6:
            raise TdxProtocolError(f"代码必须 6 字节，实际 {len(code)}")
        return struct.pack(
            "<HIHHHH6sHHHHIIH",
            0x10C,
            0x01016408,
            0x1C,
            0x1C,
            0x052D,
            market,
            code,
            category,
            1,
            int(start),
            int(count),
            0,
            0,
            0,
        )

    def _recv_response(self) -> bytes:
        assert self._sock is not None
        response = b""
        while True:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise TdxProtocolError("服务端在读取响应时关闭了连接")
            response += chunk
            if len(response) >= 16:
                body_len = struct.unpack("<H", response[12:14])[0]
                if len(response) >= 16 + body_len:
                    return response

    # ── 解析 ──────────────────────────────────────────────────────────────────

    @classmethod
    def _parse_kline_response(
        cls, response: bytes, *, period: KlinePeriod, full_code: str
    ) -> list[MarketBar]:
        if len(response) < 18:
            return []
        body = response[16:]
        if len(body) < 2:
            return []
        ret_count = struct.unpack("<H", body[:2])[0]
        pos = 2
        pre_diff_base = 0
        bars: list[MarketBar] = []
        category = PERIOD_TO_CATEGORY[period]
        for _ in range(ret_count):
            if pos >= len(body):
                break
            year, month, day, hour, minute, pos = cls._decode_datetime(category, body, pos)
            try:
                open_diff, pos = cls._decode_price(body, pos)
                close_diff, pos = cls._decode_price(body, pos)
                high_diff, pos = cls._decode_price(body, pos)
                low_diff, pos = cls._decode_price(body, pos)
            except (IndexError, struct.error):
                break
            if pos + 8 > len(body):
                break
            vol_raw = struct.unpack("<I", body[pos : pos + 4])[0]
            pos += 4
            amt_raw = struct.unpack("<I", body[pos : pos + 4])[0]
            pos += 4
            vol = cls._decode_volume(vol_raw)
            amount = cls._decode_volume(amt_raw)

            open_abs = open_diff + pre_diff_base
            close_abs = open_abs + close_diff
            high_abs = open_abs + high_diff
            low_abs = open_abs + low_diff
            pre_diff_base = close_abs

            # 简单合法性校验，避免错位生成垃圾数据
            if not (2000 <= year <= 2099):
                break
            if open_abs <= 0 or close_abs <= 0 or high_abs < low_abs:
                break

            try:
                bar_time = (
                    datetime(year, month, day)
                    if category in (TDX_CATEGORY_DAY, TDX_CATEGORY_WEEK, TDX_CATEGORY_MONTH)
                    else datetime(year, month, day, hour, minute)
                )
            except ValueError:
                continue

            bars.append(
                MarketBar(
                    full_code=full_code,
                    period=period,
                    bar_time=bar_time,
                    open=Decimal(open_abs) / Decimal(1000),
                    high=Decimal(high_abs) / Decimal(1000),
                    low=Decimal(low_abs) / Decimal(1000),
                    close=Decimal(close_abs) / Decimal(1000),
                    volume=int(vol),
                    amount=Decimal(str(round(amount, 2))),
                )
            )
        return bars

    @staticmethod
    def _decode_price(data: bytes, pos: int) -> tuple[int, int]:
        """TDX 差分价格变长编码（参考 pytdx.helper.get_price）。"""
        pos_bit = 6
        b = data[pos]
        intdata = b & 0x3F
        sign = bool(b & 0x40)
        if b & 0x80:
            while True:
                pos += 1
                b = data[pos]
                intdata += (b & 0x7F) << pos_bit
                pos_bit += 7
                if not (b & 0x80):
                    break
        pos += 1
        if sign:
            intdata = -intdata
        return intdata, pos

    @staticmethod
    def _decode_volume(ivol: int) -> float:
        """TDX 成交量对数编码（参考 pytdx.helper.get_volume）。"""
        logpoint = ivol >> 24
        hleax = (ivol >> 16) & 0xFF
        lheax = (ivol >> 8) & 0xFF
        lleax = ivol & 0xFF
        dw_ecx = logpoint * 2 - 0x7F
        dw_edx = logpoint * 2 - 0x86
        dw_esi = logpoint * 2 - 0x8E
        dw_eax = logpoint * 2 - 0x96
        dbl_xmm6 = 1.0 / pow(2.0, -dw_ecx) if dw_ecx < 0 else pow(2.0, dw_ecx)
        if hleax > 0x80:
            dbl_xmm0 = pow(2.0, dw_edx) * 128.0 + (hleax & 0x7F) * pow(2.0, dw_edx + 1)
        else:
            dbl_xmm0 = pow(2.0, dw_edx) * hleax if dw_edx >= 0 else (1.0 / pow(2.0, dw_edx)) * hleax
        dbl_xmm3 = pow(2.0, dw_esi) * lheax
        dbl_xmm1 = pow(2.0, dw_eax) * lleax
        if hleax & 0x80:
            dbl_xmm3 *= 2.0
            dbl_xmm1 *= 2.0
        return dbl_xmm6 + dbl_xmm0 + dbl_xmm3 + dbl_xmm1

    @staticmethod
    def _decode_datetime(
        category: int, data: bytes, pos: int
    ) -> tuple[int, int, int, int, int, int]:
        if category < 4 or category in (7, 8):
            zipday, tminutes = struct.unpack("<HH", data[pos : pos + 4])
            year = (zipday >> 11) + 2004
            month = (zipday % 2048) // 100
            day = (zipday % 2048) % 100
            hour = tminutes // 60
            minute = tminutes % 60
        else:
            (zipday,) = struct.unpack("<I", data[pos : pos + 4])
            year = zipday // 10000
            month = (zipday % 10000) // 100
            day = zipday % 100
            hour = 15
            minute = 0
        return year, month, day, hour, minute, pos + 4

    # ── 工具 ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _iter_chunks(items: Iterable[str], size: int) -> Iterable[list[str]]:
        bucket: list[str] = []
        for it in items:
            bucket.append(it)
            if len(bucket) >= size:
                yield bucket
                bucket = []
        if bucket:
            yield bucket
