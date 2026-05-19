"""批次进度统计单测。"""
from __future__ import annotations

from iquant_annotation_service.models import LabelBatchORM, LabelQueueItemORM
from iquant_annotation_service.usecases.batches import _progress


def test_progress_counts_current_index() -> None:
    batch = LabelBatchORM(batch_size=3, period="day", status="active")
    batch.items = [
        LabelQueueItemORM(sort_order=0, full_code="sz300001", status="completed"),
        LabelQueueItemORM(sort_order=1, full_code="sz300002", status="skipped"),
        LabelQueueItemORM(sort_order=2, full_code="sz300003", status="pending"),
    ]
    p = _progress(batch)
    assert p.total == 3
    assert p.completed == 1
    assert p.skipped == 1
    assert p.pending == 1
    assert p.current_index == 3
