"""Alembic 环境入口。

通过 ``alembic -n <section>`` 区分业务主库（默认）与时序库（``timescale``）。
两侧 ORM 使用不同的 ``MetaData``（PgBase / TsBase），避免相互污染。
"""
from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 用环境变量覆盖 sqlalchemy.url，方便容器内 / 本机切换
env_var = "IQUANT_TS_DSN_SYNC" if config.config_ini_section == "timescale" else "IQUANT_PG_DSN_SYNC"
if env_var in os.environ:
    config.set_main_option("sqlalchemy.url", os.environ[env_var])

# 导入模型以填充 metadata
from iquant_market_service.models.base import PgBase, TsBase  # noqa: E402
from iquant_market_service.models import (  # noqa: E402, F401
    MarketBarORM,
    MarketImportState,
    MarketImportTask,
    SymbolORM,
    TdxHostORM,
)

if config.config_ini_section == "timescale":
    target_metadata = TsBase.metadata
else:
    target_metadata = PgBase.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    cfg = config.get_section(config.config_ini_section) or {}
    connectable = engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
