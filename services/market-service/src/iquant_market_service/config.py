"""行情服务配置。

通过环境变量注入，禁止把配置写死在代码里。
"""
from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MarketSettings(BaseSettings):
    """行情服务配置。"""

    model_config = SettingsConfigDict(env_prefix="IQUANT_", extra="ignore")

    # 业务主库（symbol、import_task、import_state、tdx_host 等元数据）
    pg_dsn: str = Field(
        default="postgresql+asyncpg://iquant:iquant_dev_pwd@postgres:5432/iquant"
    )

    # 时序行情库（market_bar hypertable）
    ts_dsn: str = Field(
        default="postgresql+asyncpg://iquant:iquant_dev_pwd@timescaledb:5432/iquant_market"
    )

    # Redis（缓存 + 分布式锁 + Celery broker）
    redis_url: str = Field(default="redis://redis:6379/0")

    # 通达信本地数据目录（vipdoc）
    tdx_vipdoc_dir: str = Field(default="/data/tdx/vipdoc")

    # 通达信主站配置文件
    tdx_hosts_config: Path = Field(default=Path("/workspace/storage/local/tdx_hosts.json"))

    # 在线 TDX 连接池
    tdx_pool_size: int = 4
    tdx_connect_timeout: float = 5.0
    tdx_read_timeout: float = 10.0


_settings: MarketSettings | None = None


def get_market_settings() -> MarketSettings:
    """单例配置访问器。"""
    global _settings
    if _settings is None:
        _settings = MarketSettings()
    return _settings
