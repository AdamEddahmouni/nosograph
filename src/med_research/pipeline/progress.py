"""Standard pipeline progress callback helpers."""

from __future__ import annotations

from collections.abc import Callable

from med_research.logging_config import get_logger

StandardProgress = Callable[[str, int, int], None]

logger = get_logger(__name__)


def _tick(cb: StandardProgress | None, step: str, i: int, n: int) -> None:
    if cb:
        cb(step, i, n)


def cli_progress(step: str, current: int, total: int) -> None:
    """Log a standard ``(step, current, total)`` tick for CLI entry points."""
    if total > 1:
        logger.info("  %s (%d/%d)", step, current, total)
    else:
        logger.info("  %s", step)
