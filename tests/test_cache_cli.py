"""Unit tests for med-research cache CLI commands (stats, clear, cleanup)."""

from __future__ import annotations

import json
import time
from types import SimpleNamespace

import pytest

from med_research.cache import CacheManager


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    """Point all CacheManager() calls at an isolated temp directory."""
    path = tmp_path / "cache"

    def _manager(*_args, **_kwargs):
        return CacheManager(
            cache_dir=_kwargs.get("cache_dir", path),
            ttl_seconds=_kwargs.get("ttl_seconds", 86400),
        )

    monkeypatch.setattr("med_research.cache.CacheManager", _manager)
    return path


def _write_entry(cache_dir, namespace: str, key: str, data: dict, age_seconds: float = 0) -> None:
    mgr = CacheManager(cache_dir=cache_dir)
    mgr.set(namespace, key, data)
    if age_seconds > 0:
        cache_file = next(cache_dir.glob(f"{namespace}/*.json"))
        entry = json.loads(cache_file.read_text(encoding="utf-8"))
        entry["timestamp"] = time.time() - age_seconds
        cache_file.write_text(json.dumps(entry), encoding="utf-8")


def test_cache_stats_reports_entries(cache_dir, caplog):
    from med_research.cli import cmd_cache

    _write_entry(cache_dir, "ns1", "a", {"v": 1})
    _write_entry(cache_dir, "ns2", "b", {"v": 2})

    assert cmd_cache(SimpleNamespace(cache_action="stats")) == 0
    assert "Total cached entries: 2" in caplog.text
    assert "ns1" in caplog.text
    assert "ns2" in caplog.text


def test_cache_clear_all(cache_dir, caplog):
    from med_research.cli import cmd_cache

    _write_entry(cache_dir, "ns1", "a", {"v": 1})
    _write_entry(cache_dir, "ns2", "b", {"v": 2})

    assert cmd_cache(SimpleNamespace(cache_action="clear", namespace=None)) == 0
    assert "Cleared 2 cache entries" in caplog.text
    assert CacheManager(cache_dir=cache_dir).stats()["total_entries"] == 0


def test_cache_clear_namespace(cache_dir, caplog):
    from med_research.cli import cmd_cache

    _write_entry(cache_dir, "keep", "a", {"v": 1})
    _write_entry(cache_dir, "drop", "b", {"v": 2})

    assert cmd_cache(SimpleNamespace(cache_action="clear", namespace="drop")) == 0
    assert "Cleared 1 cache entries" in caplog.text
    stats = CacheManager(cache_dir=cache_dir).stats()
    assert stats["total_entries"] == 1
    assert "keep" in stats["namespaces"]


def test_cache_cleanup_removes_expired(cache_dir, caplog):
    from med_research.cli import cmd_cache

    _write_entry(cache_dir, "ns", "fresh", {"ok": True})
    _write_entry(cache_dir, "ns", "stale", {"old": True}, age_seconds=99999)

    assert cmd_cache(SimpleNamespace(cache_action="cleanup", ttl=None)) == 0
    assert "Removed 1 expired entries" in caplog.text
    assert CacheManager(cache_dir=cache_dir).stats()["total_entries"] == 1


def test_cache_unknown_action_shows_usage(cache_dir, caplog):
    from med_research.cli import cmd_cache

    assert cmd_cache(SimpleNamespace(cache_action=None)) == 0
    assert "med-research cache {stats|clear|cleanup|migrate}" in caplog.text
