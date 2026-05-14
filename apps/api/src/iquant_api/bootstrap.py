"""应用启动期配置：日志、CORS、错误处理、celery client。"""
from __future__ import annotations

import logging
import sys

import structlog
from celery import Celery
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from iquant_domain.errors import IquantError
from iquant_market_service.config import get_market_settings


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        stream=sys.stdout,
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )


def install_cors(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 开发期；生产应替换为白名单
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(IquantError)
    async def _iquant_error_handler(_request: Request, exc: IquantError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(Exception)
    async def _generic_handler(_request: Request, exc: Exception) -> JSONResponse:
        logging.getLogger(__name__).exception("unhandled_exception", exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": {"code": "INTERNAL_ERROR", "message": "服务内部错误"}},
        )


_celery_client: Celery | None = None


def get_celery_client() -> Celery:
    """API 进程只用 Celery 投递任务，不执行任务。"""
    global _celery_client
    if _celery_client is None:
        s = get_market_settings()
        broker = __import__("os").environ.get("IQUANT_CELERY_BROKER_URL", s.redis_url)
        result_backend = __import__("os").environ.get(
            "IQUANT_CELERY_RESULT_BACKEND", s.redis_url
        )
        _celery_client = Celery("iquant", broker=broker, backend=result_backend)
    return _celery_client


def enqueue_market_import(task_id: str) -> None:
    """投递行情导入任务到 Celery worker。任务名与 worker 端一致。"""
    get_celery_client().send_task(
        "market.import_local", args=[task_id], queue="market", task_id=task_id
    )
