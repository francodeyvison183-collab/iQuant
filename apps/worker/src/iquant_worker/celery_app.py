"""Celery 应用实例。

任务模块通过 ``include`` 注册，便于按需扩展（后续 strategy / backtest 等任务同理）。
"""
from __future__ import annotations

import os

from celery import Celery


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


broker_url = _env("IQUANT_CELERY_BROKER_URL", "redis://redis:6379/1")
result_backend = _env("IQUANT_CELERY_RESULT_BACKEND", "redis://redis:6379/2")

app = Celery(
    "iquant",
    broker=broker_url,
    backend=result_backend,
    include=["iquant_worker.tasks.market"],
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
    }
