"""导入任务与导入状态仓储。"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy import desc, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    MarketImportState,
    MarketImportTask,
    MarketImportTaskStatus,
    MarketImportTaskType,
)


class ImportTaskRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def create(
        self,
        *,
        task_id: str,
        task_type: MarketImportTaskType,
        params: dict,
    ) -> MarketImportTask:
        row = MarketImportTask(
            task_id=task_id,
            task_type=task_type.value,
            status=MarketImportTaskStatus.QUEUED.value,
            params=params,
        )
        self.s.add(row)
        await self.s.flush()
        return row

    async def get(self, task_id: str) -> MarketImportTask | None:
        return (
            await self.s.execute(
                select(MarketImportTask).where(MarketImportTask.task_id == task_id)
            )
        ).scalar_one_or_none()

    async def list_paged(
        self,
        *,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[MarketImportTask], int]:
        q = select(MarketImportTask)
        c = select(func.count()).select_from(MarketImportTask)
        if status:
            q = q.where(MarketImportTask.status == status)
            c = c.where(MarketImportTask.status == status)
        q = q.order_by(desc(MarketImportTask.created_at)).limit(limit).offset(offset)
        rows = list((await self.s.execute(q)).scalars().all())
        total = int((await self.s.execute(c)).scalar_one())
        return rows, total

    async def mark_running(self, task_id: str) -> None:
        row = await self.get(task_id)
        if row and row.status == MarketImportTaskStatus.QUEUED.value:
            row.status = MarketImportTaskStatus.RUNNING.value
            row.started_at = datetime.now()

    async def update_progress(
        self,
        task_id: str,
        *,
        total_files: int | None = None,
        done_files: int | None = None,
        imported_bars: int | None = None,
        error_count: int | None = None,
    ) -> None:
        row = await self.get(task_id)
        if row is None:
            return
        if total_files is not None:
            row.total_files = total_files
        if done_files is not None:
            row.done_files = done_files
        if imported_bars is not None:
            row.imported_bars = imported_bars
        if error_count is not None:
            row.error_count = error_count

    async def mark_finished(
        self,
        task_id: str,
        *,
        status: MarketImportTaskStatus,
        error_message: str | None = None,
    ) -> None:
        row = await self.get(task_id)
        if row is None:
            return
        row.status = status.value
        row.finished_at = datetime.now()
        if error_message:
            row.error_message = error_message[:2000]

    async def reset(self, task_id: str) -> MarketImportTask | None:
        """重置任务状态为 queued，清空进度，准备重跑。"""
        row = await self.get(task_id)
        if row is None:
            return None
        row.status = MarketImportTaskStatus.QUEUED.value
        row.done_files = 0
        row.imported_bars = 0
        row.error_count = 0
        row.error_message = None
        row.started_at = None
        row.finished_at = None
        await self.s.flush()
        return row


class ImportStateRepo:
    """文件级导入状态。"""

    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def load_state_map(
        self, file_paths: Iterable[str] | None = None
    ) -> dict[str, tuple[int, float, int]]:
        """``{file_path: (file_size, file_mtime, imported_records)}``。"""
        q = select(MarketImportState)
        if file_paths is not None:
            q = q.where(MarketImportState.file_path.in_(list(file_paths)))
        rows = (await self.s.execute(q)).scalars().all()
        return {
            r.file_path: (r.file_size, r.file_mtime, r.imported_records)
            for r in rows
        }

    async def upsert(
        self,
        *,
        file_path: str,
        full_code: str,
        period: str,
        file_size: int,
        file_mtime: float,
        imported_records: int,
        last_bar_time: datetime | None,
        last_task_id: str | None,
    ) -> None:
        stmt = (
            pg_insert(MarketImportState)
            .values(
                file_path=file_path,
                full_code=full_code,
                period=period,
                file_size=file_size,
                file_mtime=file_mtime,
                imported_records=imported_records,
                last_bar_time=last_bar_time,
                last_task_id=last_task_id,
            )
            .on_conflict_do_update(
                index_elements=[MarketImportState.file_path],
                set_={
                    "file_size": file_size,
                    "file_mtime": file_mtime,
                    "imported_records": imported_records,
                    "last_bar_time": last_bar_time,
                    "last_task_id": last_task_id,
                },
            )
        )
        await self.s.execute(stmt)
