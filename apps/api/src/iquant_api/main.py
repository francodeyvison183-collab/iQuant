"""iQuant FastAPI 应用入口。

只做装配，不写业务逻辑。业务逻辑分布在 ``services/*`` 用例与 ``packages/*`` 算法层。
"""
from __future__ import annotations

import os

from fastapi import FastAPI

from .bootstrap import configure_logging, install_cors, install_error_handlers
from .routes.v1 import admin_market, health


def create_app() -> FastAPI:
    configure_logging(os.environ.get("IQUANT_API_LOG_LEVEL", "INFO"))

    app = FastAPI(
        title="iQuant API",
        version="0.1.0",
        description="iQuant 服务端 REST API。MVP 阶段先暴露行情后台管理与健康检查。",
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    install_cors(app)
    install_error_handlers(app)

    app.include_router(health.router)
    app.include_router(admin_market.router, prefix="/api/v1")

    return app


app = create_app()
