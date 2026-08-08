"""Unit tests for CacheManager and cache helper utilities."""

from __future__ import annotations

import json
import time

import pytest

from med_research.cache import (
    NS_GEO,
    NS_GWAS,
    CacheManager,
    cache_get,
    cache_set,
    env_use_cache,
    get_cache_manager,
    load_legacy_json,
)
from med_research.exceptions import CacheCorruptionError


@pytest.fixture
def cache_dir(tmp_path):
    return tmp_path / "cache"


@pytest.fixture
def mgr(cache_dir):
    return CacheManager(cache_dir=cache_dir, ttl_seconds=3600)


def test_cache_hit_and_miss(mgr):
    assert mgr.get("ns", "missing") is None
    mgr.set("ns", "key", {"value": 1})
    assert mgr.get("ns", "key") == {"value": 1}


def test_cache_namespace_isolation(mgr):
    mgr.set("alpha", "k", "a")
    mgr.set("beta", "k", "b")
    assert mgr.get("alpha", "k") == "a"
    assert mgr.get("beta", "k") == "b"


def test_cache_ttl_expiry(cache_dir):
    mgr = CacheManager(cache_dir=cache_dir, ttl_seconds=60)
    mgr.set("ns", "stale", {"old": True})
    cache_file = next(cache_dir.glob("ns/*.json"))
    entry = json.loads(cache_file.read_text(encoding="utf-8"))
    entry["timestamp"] = time.time() - 120
    cache_file.write_text(json.dumps(entry), encoding="utf-8")
    assert mgr.get("ns", "stale") is None


def test_cache_corruption_missing_timestamp_raises(mgr):
    path = mgr._cache_path("ns", "bad")
    path.write_text(json.dumps({"data": {}}), encoding="utf-8")
    with pytest.raises(CacheCorruptionError):
        mgr.get("ns", "bad")


def test_cache_corrupt_json_returns_none(mgr):
    path = mgr._cache_path("ns", "broken")
    path.write_text("{not json", encoding="utf-8")
    assert mgr.get("ns", "broken") is None


def test_cache_clear_namespace(mgr):
    mgr.set("keep", "a", 1)
    mgr.set("drop", "b", 2)
    removed = mgr.clear("drop")
    assert removed == 1
    assert mgr.get("drop", "b") is None
    assert mgr.get("keep", "a") == 1


def test_cache_stats(mgr):
    mgr.set("ns1", "a", 1)
    mgr.set("ns2", "b", 2)
    stats = mgr.stats()
    assert stats["total_entries"] == 2
    assert "ns1" in stats["namespaces"]
    assert "ns2" in stats["namespaces"]


def test_cache_cleanup_removes_expired(cache_dir):
    mgr = CacheManager(cache_dir=cache_dir, ttl_seconds=60)
    mgr.set("ns", "fresh", {"ok": True})
    mgr.set("ns", "stale", {"old": True})
    stale_file = mgr._cache_path("ns", "stale")
    entry = json.loads(stale_file.read_text(encoding="utf-8"))
    entry["timestamp"] = time.time() - 9999
    stale_file.write_text(json.dumps(entry), encoding="utf-8")
    removed = mgr.cleanup(ttl_seconds=60)
    assert removed == 1
    assert mgr.stats()["total_entries"] == 1


def test_cache_get_bypass_when_use_cache_false(cache_dir, monkeypatch):
    monkeypatch.setattr(
        "med_research.cache.get_cache_manager",
        lambda: CacheManager(cache_dir=cache_dir),
    )
    cache_set(NS_GWAS, "sle", {"gwas_results": {}}, use_cache=True)
    assert cache_get(NS_GWAS, "sle", use_cache=False) is None


def test_env_use_cache_defaults_true(monkeypatch):
    monkeypatch.delenv("USE_CACHE", raising=False)
    assert env_use_cache() is True


def test_cache_get_respects_use_cache_env(cache_dir, monkeypatch):
    monkeypatch.setenv("USE_CACHE", "false")
    monkeypatch.setattr("med_research.cache._DEFAULT_MANAGER", None)
    mgr = CacheManager(cache_dir=cache_dir, respect_env_use_cache=True)
    monkeypatch.setattr("med_research.cache.get_cache_manager", lambda: mgr)
    mgr.set(NS_GWAS, "sle", {"gwas_results": {}})
    assert cache_get(NS_GWAS, "sle", use_cache=True) is None
    assert mgr.get(NS_GWAS, "sle") is None


def test_cache_set_respects_use_cache_env(cache_dir, monkeypatch):
    monkeypatch.setenv("USE_CACHE", "false")
    monkeypatch.setattr("med_research.cache._DEFAULT_MANAGER", None)
    mgr = CacheManager(cache_dir=cache_dir, respect_env_use_cache=True)
    monkeypatch.setattr("med_research.cache.get_cache_manager", lambda: mgr)
    cache_set(NS_GWAS, "sle", {"gwas_results": {}}, use_cache=True)
    assert mgr.stats()["total_entries"] == 0


def test_explicit_cache_manager_bypasses_use_cache_env(cache_dir, monkeypatch):
    monkeypatch.setenv("USE_CACHE", "false")
    mgr = CacheManager(cache_dir=cache_dir, respect_env_use_cache=False)
    cache_set(NS_GWAS, "sle", {"gwas_results": {}}, use_cache=True, cache=mgr)
    assert cache_get(NS_GWAS, "sle", use_cache=True, cache=mgr) == {"gwas_results": {}}


def test_get_cache_manager_singleton_respects_env(cache_dir, monkeypatch):
    monkeypatch.setenv("USE_CACHE", "false")
    monkeypatch.setattr("med_research.cache.DEFAULT_CACHE_DIR", cache_dir)
    monkeypatch.setattr("med_research.cache._DEFAULT_MANAGER", None)
    mgr = get_cache_manager()
    mgr.set(NS_GWAS, "sle", {"gwas_results": {}})
    assert mgr.stats()["total_entries"] == 0


def test_load_legacy_json(tmp_path):
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    assert load_legacy_json(path) == [1, 2, 3]
    assert load_legacy_json(tmp_path / "missing.json") is None


def test_write_json_atomic_replaces_target(tmp_path):
    from med_research.cache import write_json_atomic

    target = tmp_path / "output.json"
    write_json_atomic(target, {"version": 1})
    write_json_atomic(target, {"version": 2})
    assert json.loads(target.read_text(encoding="utf-8")) == {"version": 2}
    assert not list(tmp_path.glob("*.tmp"))


def test_disease_output_path_format(tmp_path):
    from med_research.cache import disease_output_path

    path = disease_output_path(tmp_path, "expression_correlations", "ra")
    assert path == tmp_path / "expression_correlations_ra.json"


def test_module_namespace_constants():
    assert NS_GWAS == "gwas"
    assert NS_GEO == "geo"


def test_safe_key_filename_handles_windows_invalid_chars(mgr):
    path = mgr._cache_path(
        "enrichment",
        "GENE1,GENE2|||[\"GO_Biological_Process_2023\"]|||15",
    )
    assert "|" not in path.name
    assert '"' not in path.name
    mgr.set("enrichment", "GENE1,GENE2|||[\"GO\"]|||15", {"ok": True})
    assert mgr.get("enrichment", "GENE1,GENE2|||[\"GO\"]|||15") == {"ok": True}
