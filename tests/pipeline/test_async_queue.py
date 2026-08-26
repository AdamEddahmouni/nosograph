"""Unit tests for Async Job Queue engine."""

import datetime
import time

import pytest

from med_research.pipeline.async_queue import AsyncJobQueue, TaskStatus

pytestmark = pytest.mark.unit


def _assert_aware_utc(value: str) -> datetime.datetime:
    parsed = datetime.datetime.fromisoformat(value)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == datetime.timedelta(0)
    return parsed


def test_task_timestamps_carry_explicit_utc_offset():
    queue = AsyncJobQueue(max_workers=2)
    task = queue.create_task("test_utc")
    created = _assert_aware_utc(task.created_at)

    queue.submit(task.task_id, lambda: "ok")

    max_wait = 2.0
    start = time.time()
    while time.time() - start < max_wait:
        t = queue.get_task(task.task_id)
        if t and t.status == TaskStatus.COMPLETED:
            break
        time.sleep(0.05)

    completed = queue.get_task(task.task_id)
    assert completed is not None
    assert completed.status == TaskStatus.COMPLETED
    started = _assert_aware_utc(completed.started_at or "")
    finished = _assert_aware_utc(completed.completed_at or "")
    assert created <= started <= finished


def test_async_job_lifecycle():
    queue = AsyncJobQueue(max_workers=2)
    task = queue.create_task("test_compute", {"param1": "val1"})
    assert task.status == TaskStatus.PENDING
    assert task.progress == 0.0

    def dummy_work(x: int) -> int:
        return x * 2

    queue.submit(task.task_id, dummy_work, 21)

    # Wait briefly for worker thread
    max_wait = 2.0
    start = time.time()
    while time.time() - start < max_wait:
        t = queue.get_task(task.task_id)
        if t and t.status == TaskStatus.COMPLETED:
            break
        time.sleep(0.05)

    completed_task = queue.get_task(task.task_id)
    assert completed_task is not None
    assert completed_task.status == TaskStatus.COMPLETED
    assert completed_task.result == 42
    assert completed_task.progress == 1.0


def test_async_job_failure():
    queue = AsyncJobQueue(max_workers=2)
    task = queue.create_task("test_failing")

    def error_work():
        raise ValueError("Computation failed")

    queue.submit(task.task_id, error_work)

    max_wait = 2.0
    start = time.time()
    while time.time() - start < max_wait:
        t = queue.get_task(task.task_id)
        if t and t.status == TaskStatus.FAILED:
            break
        time.sleep(0.05)

    failed_task = queue.get_task(task.task_id)
    assert failed_task is not None
    assert failed_task.status == TaskStatus.FAILED
    assert "Computation failed" in (failed_task.error or "")
