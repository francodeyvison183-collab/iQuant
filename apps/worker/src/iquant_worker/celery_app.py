"""Celery 应用实例。

任务模块通过 ``include`` 注册，便于按需扩展（后续 strategy / backtest 等任务同理）。
"""
from __future__ import annotations

import os

from celery import Celery
from celery.signals import beat_init, worker_init

from iquant_worker.error_logging import attach_error_log_file


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


broker_url = _env("IQUANT_CELERY_BROKER_URL", "redis://redis:6379/1")
result_backend = _env("IQUANT_CELERY_RESULT_BACKEND", "redis://redis:6379/2")

app = Celery(
    "iquant",
    broker=broker_url,
    backend=result_backend,
    include=["iquant_worker.tasks.market", "iquant_worker.tasks.strategy"],
)

app.conf.update(
    task_default_queue="default",
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_max_tasks_per_child=200,
    broker_connection_retry_on_startup=True,
    timezone=_env("TZ", "Asia/Shanghai"),
    enable_utc=False,
    task_routes={
        "market.*": {"queue": "market"},
        "strategy.*": {"queue": "default"},
    },
)


@app.on_after_configure.connect
def setup_schedules(sender, **_kwargs):  # type: ignore[no-untyped-def]
    # 行情主站每小时测速一次；增量导入每个交易日盘后 16:30 触发
    sender.conf.beat_schedule = {
        "tdx-hosts-test-hourly": {
            "task": "market.test_hosts",
            "schedule": 3600.0,
            "options": {"queue": "market"},
        },
        "market-incremental-daily": {
            "task": "market.import_local",
            "schedule": __import__("celery.schedules", fromlist=["crontab"]).crontab(
                hour=16, minute=30, day_of_week="mon,tue,wed,thu,fri"
            ),
            "kwargs": {"task_id": "scheduled-auto-incremental"},
            "options": {"queue": "market"},
        },
        "symbol-names-daily": {
            "task": "market.sync_symbols",
            "schedule": __import__("celery.schedules", fromlist=["crontab"]).crontab(
                hour=8, minute=0, day_of_week="mon,tue,wed,thu,fri"
            ),
            "options": {"queue": "market"},
        },
    }


@worker_init.connect
@beat_init.connect
def _setup_error_file_logging(**_kwargs) -> None:
    attach_error_log_file(_env("IQUANT_WORKER_ERROR_LOG_PATH", "logs/iquant-worker-errors.log"))
