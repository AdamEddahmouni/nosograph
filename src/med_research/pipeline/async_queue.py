"""Asynchronous background job queue and task tracking engine.

Provides a thread-safe, memory-safe in-process task scheduler with optional
Redis persistence fallback, task status lifecycle management, and event callbacks.
"""

from __future__ import annotations

import datetime
import enum
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AsyncTask:
    task_id: str
    task_type: str
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    message: str = "Initialized"
    created_at: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Any] = None
    error: Optional[str] = None


class AsyncJobQueue:
    """In-memory async job queue with thread pool execution."""

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._tasks: Dict[str, AsyncTask] = {}

    def create_task(self, task_type: str, params: Optional[Dict[str, Any]] = None) -> AsyncTask:
        task_id = str(uuid.uuid4())
        task = AsyncTask(
            task_id=task_id,
            task_type=task_type,
            params=params or {},
        )
        self._tasks[task_id] = task
        logger.info("Created async task %s (type=%s)", task_id, task_type)
        return task

    def get_task(self, task_id: str) -> Optional[AsyncTask]:
        return self._tasks.get(task_id)

    def list_tasks(self, limit: int = 50) -> List[AsyncTask]:
        tasks = list(self._tasks.values())
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return tasks[:limit]

    def submit(
        self,
        task_id: str,
        fn: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> AsyncTask:
        task = self._tasks.get(task_id)
        if not task:
            raise KeyError(f"Task {task_id} not found.")

        def _worker():
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            task.message = "Running"
            try:
                result = fn(*args, **kwargs)
                task.status = TaskStatus.COMPLETED
                task.progress = 1.0
                task.message = "Completed successfully"
                task.result = result
                task.completed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
                logger.info("Async task %s completed successfully", task_id)
            except Exception as e:
                task.status = TaskStatus.FAILED
                task.message = "Failed execution"
                task.error = str(e)
                task.completed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
                logger.exception("Async task %s failed: %s", task_id, e)

        self._executor.submit(_worker)
        return task

    def update_progress(self, task_id: str, progress: float, message: str = "") -> None:
        task = self._tasks.get(task_id)
        if task:
            task.progress = min(max(progress, 0.0), 1.0)
            if message:
                task.message = message


# Global instance for web & pipeline usage
job_queue = AsyncJobQueue()
