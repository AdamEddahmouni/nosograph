"""Memory-aware cap on the pytest-xdist worker pool.

``-n auto`` sizes the pool from CPU count alone. On a many-core machine with
little free RAM that oversubscribes memory, the OS kills a worker mid-test, and
only the test it happened to be running is reported — so the failure set moves
between runs instead of reproducing. ``tests/conftest.py`` lowers the count to
what available memory can hold.
"""

from __future__ import annotations

import pytest

from tests import conftest

pytestmark = pytest.mark.unit


def test_available_memory_is_readable_or_reported_unknown():
    """The probe must return a plausible reading or None, never raise."""
    value = conftest._available_memory_mb()

    assert value is None or value > 0


def test_budget_scales_with_available_memory(monkeypatch):
    monkeypatch.setattr(conftest, "_available_memory_mb", lambda: 10_000)

    # (10_000 MiB free - 1_024 MiB reserved) // 600 MiB per worker
    assert conftest._xdist_worker_budget_workers() == 14


def test_budget_never_drops_below_one_worker(monkeypatch):
    """Memory exhaustion must not disable distribution entirely."""
    monkeypatch.setattr(conftest, "_available_memory_mb", lambda: 0)

    assert conftest._xdist_worker_budget_workers() == 1


def test_budget_is_unknown_when_memory_is_unreadable(monkeypatch):
    monkeypatch.setattr(conftest, "_available_memory_mb", lambda: None)

    assert conftest._xdist_worker_budget_workers() is None


def test_hook_caps_the_pool_below_cpu_count(monkeypatch):
    monkeypatch.delenv("PYTEST_XDIST_AUTO_NUM_WORKERS", raising=False)
    monkeypatch.setattr(conftest.os, "cpu_count", lambda: 32)
    monkeypatch.setattr(conftest, "_available_memory_mb", lambda: 4_000)

    # (4_000 - 1_024) // 600 == 4 workers rather than the 32 CPUs
    assert conftest.pytest_xdist_auto_num_workers(None) == 4


def test_hook_defers_when_memory_is_ample(monkeypatch):
    """With room to spare the hook must not change xdist's own count."""
    monkeypatch.delenv("PYTEST_XDIST_AUTO_NUM_WORKERS", raising=False)
    monkeypatch.setattr(conftest.os, "cpu_count", lambda: 4)
    monkeypatch.setattr(conftest, "_available_memory_mb", lambda: 64_000)

    assert conftest.pytest_xdist_auto_num_workers(None) is None


def test_hook_defers_when_memory_is_unknown(monkeypatch):
    """Fail open: an unreadable probe must not silently throttle CI."""
    monkeypatch.delenv("PYTEST_XDIST_AUTO_NUM_WORKERS", raising=False)
    monkeypatch.setattr(conftest, "_available_memory_mb", lambda: None)

    assert conftest.pytest_xdist_auto_num_workers(None) is None


def test_hook_defers_to_the_xdist_env_override(monkeypatch):
    """xdist's documented escape hatch wins outright, even under pressure."""
    monkeypatch.setenv("PYTEST_XDIST_AUTO_NUM_WORKERS", "2")
    monkeypatch.setattr(conftest, "_available_memory_mb", lambda: 1_000)

    assert conftest.pytest_xdist_auto_num_workers(None) is None
