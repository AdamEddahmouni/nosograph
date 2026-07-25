"""Celery tasks package."""

from web_api.tasks.analysis_tasks import celery_app

__all__ = ["celery_app"]
