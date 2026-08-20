"""Background job executor for Lead Optimization tasks."""

from concurrent.futures import ThreadPoolExecutor

_executor = ThreadPoolExecutor(max_workers=4)


def submit_job(fn, *args, **kwargs):
    """Submit a task to be executed in the background thread pool."""
    return _executor.submit(fn, *args, **kwargs)
