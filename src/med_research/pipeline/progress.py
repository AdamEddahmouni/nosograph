"""Standard pipeline progress callback helpers."""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from typing import Any

from med_research.logging_config import get_logger

StandardProgress = Callable[[str, int, int], None]

logger = get_logger(__name__)


def _tick(cb: Any, step: str, i: int, n: int) -> None:
    if not cb:
        return
    try:
        cb(step, i, n)
    except TypeError:
        with contextlib.suppress(Exception):
            cb(i / max(1, n), step)
    except Exception:
        pass


def cli_progress(step: str, current: int, total: int) -> None:
    """Log a standard ``(step, current, total)`` tick for CLI entry points."""
    if total > 1:
        logger.info("  %s (%d/%d)", step, current, total)
    else:
        logger.info("  %s", step)
