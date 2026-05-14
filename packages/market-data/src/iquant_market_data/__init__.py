"""行情数据适配层公共出口。"""
from .protocols import MarketDataSource
from .tdx.client import TdxClient
from .tdx.file_parser import parse_day_file, parse_lc5_file
from .tdx.file_scanner import TdxFileInfo, scan_changed_files, scan_tdx_files
from .tdx.host_manager import TdxHost, TdxHostManager
from .tdx.pool import TdxConnectionPool
from .tdx.source import TdxMarketDataSource

__all__ = [
    "MarketDataSource",
    "TdxClient",
    "TdxConnectionPool",
    "TdxFileInfo",
    "TdxHost",
    "TdxHostManager",
    "TdxMarketDataSource",
    "parse_day_file",
    "parse_lc5_file",
    "scan_changed_files",
    "scan_tdx_files",
]
