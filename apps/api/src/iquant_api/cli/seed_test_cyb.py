"""投递创业板（cyb）近 N 个月日 K 在线批量任务（迭代 0 测试数据集）。"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date, timedelta

from iquant_domain.market import KlinePeriod
from iquant_market_service.usecases.batch_online_fetch import enqueue_batch_online_task

from ..bootstrap import enqueue_online_batch


async def _run(*, months: int, periods: list[KlinePeriod]) -> str:
    if months < 1 or months > 24:
        raise ValueError("months 须在 1–24 之间")
    start = date.today() - timedelta(days=months * 30)
    ref = await enqueue_batch_online_task(
        markets=["cyb"],
        periods=periods,
        codes=None,
        start_date=start.isoformat(),
        end_date=None,
        enqueuer=enqueue_online_batch,
    )
    return ref.task_id


def main() -> None:
    parser = argparse.ArgumentParser(
        description="投递创业板在线批量更新（默认近 6 个月日 K）",
    )
    parser.add_argument("--months", type=int, default=6, help="回溯月数（默认 6）")
    parser.add_argument(
        "--periods",
        default="day",
        help="周期，逗号分隔，如 day 或 day,week（默认 day）",
    )
    args = parser.parse_args()
    period_map = {p.value: p for p in KlinePeriod}
    try:
        periods = [period_map[x.strip()] for x in args.periods.split(",") if x.strip()]
    except KeyError as exc:
        print(f"未知周期: {exc}", file=sys.stderr)
        sys.exit(1)
    try:
        task_id = asyncio.run(_run(months=args.months, periods=periods))
    except Exception as exc:  # noqa: BLE001
        print(f"投递失败: {exc}", file=sys.stderr)
        sys.exit(1)
    start = date.today() - timedelta(days=args.months * 30)
    print(f"已投递在线批量任务 task_id={task_id}")
    print(f"  市场: cyb（创业板 sz300/301）")
    print(f"  区间: {start.isoformat()} ~ 今天")
    print(f"  周期: {', '.join(p.value for p in periods)}")
    print("请在管理后台「数据更新」查看进度，或观察 worker 日志。")


if __name__ == "__main__":
    main()
