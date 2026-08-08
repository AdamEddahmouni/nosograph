"""Standard pipeline progress callback helpers."""

from __future__ import annotations

from collections.abc import Callable

StandardProgress = Callable[[str, int, int], None]


def _tick(cb: StandardProgress | None, step: str, i: int, n: int) -> None:
    if cb:
        cb(step, i, n)
