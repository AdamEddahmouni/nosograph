"""Celery tasks package."""

from med_research.web.tasks.analysis_tasks import celery_app

__all__ = ["celery_app"]
