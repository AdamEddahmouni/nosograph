"""Tests for the Disease Admin API (backups / prune / restore).

The scaffold engine's functions are monkeypatched so no external APIs are
called and no real disease data is modified. The knowledge-graph dependency
loaders are replaced with spies to assert cache invalidation after writes.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from med_research.web.main import app

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def client():
    """Shared TestClient (lifespan preloads the KG once, like test_web_api)."""
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def admin_mocks(monkeypatch):
    """Patch scaffold + dependency loaders; record calls and cache clears."""
    import med_research.diseases.scaffold as scaf
    import med_research.web.dependencies as deps

    state = {"prune": [], "restore": [], "backups": [], "cache_clears": 0}

    def fake_refresh(*args, **kwargs):
        if args:
            kwargs = {**kwargs, "disease_id": args[0]}
        state["prune"].append(kwargs)
        dry_run = kwargs.get("dry_run", False)
        return {
            "disease_id": kwargs["disease_id"],
            "name": "Test Disease",
            "efo_id": "EFO_0000000",
            "root": "/tmp",
            "dry_run": dry_run,
            "sources": {"opentargets": True, "gwas": True, "reactome": False},
            "merge": {
                "genes": {"added": ["NEWGENE"], "updated": [], "kept": ["TLR7"]},
                "drugs": {"added": [], "updated": [], "kept": []},
                "pathways": {"added": [], "updated": [], "kept": []},
            },
            "prune": {
                "enabled": True,
                "aborted": False,
                "genes": ["ORPHAN"],
                "drugs": [],
                "scrubbed_pathways": [],
                "backup": None if dry_run else "/tmp/data/backups/pruned_x.json",
            },
            "counts": {"genes": 5, "drugs": 2, "pathways": 3, "relationships": 10},
            "files": ["/tmp/data/genes.json"],
        }

    def fake_restore(*args, **kwargs):
        if args:
            kwargs = {**kwargs, "disease_id": args[0]}
        state["restore"].append(kwargs)
        return {
            "disease_id": kwargs["disease_id"],
            "backup": kwargs.get("backup_path") or "/tmp/data/backups/newest.json",
            "backup_disease_id": kwargs["disease_id"],
            "root": "/tmp",
            "dry_run": kwargs.get("dry_run", False),
            "restored": {"genes": ["ORPHAN"], "drugs": []},
            "skipped": {"genes": [], "drugs": []},
            "updated_pathways": ["jak-stat"],
            "counts": {"genes": 6, "drugs": 2, "pathways": 3, "relationships": 11},
            "files": ["/tmp/data/genes.json"],
        }

    def fake_list_backups(disease_id, target_dir=None):
        state["backups"].append(disease_id)
        return {
            "disease_id": disease_id,
            "count": 1,
            "total_size_bytes": 586,
            "backups": [
                {
                    "path": "/tmp/data/backups/pruned_sle_20260101_000000_000000.json",
                    "size_bytes": 586,
                    "modified": "2026-01-01T00:00:00",
                    "genes": ["ORPHAN"],
                    "drugs": [],
                    "readable": True,
                }
            ],
        }

    monkeypatch.setattr(scaf, "refresh_disease", fake_refresh)
    monkeypatch.setattr(scaf, "restore_disease", fake_restore)
    monkeypatch.setattr(scaf, "list_backups", fake_list_backups)

    class FakeCache:
        def cache_clear(self):
            state["cache_clears"] += 1

    for name in ("get_knowledge_graph", "get_kg_genes", "get_kg_drugs", "get_kg_pathways"):
        monkeypatch.setattr(deps, name, FakeCache())

    return state


# ── Backups ──────────────────────────────────────────────────────────────


class TestAdminBackups:
    def test_lists_backups(self, client, admin_mocks):
        resp = client.get("/api/admin/diseases/sle/backups")
        assert resp.status_code == 200
        data = resp.json()
        assert data["disease_id"] == "sle"
        assert data["count"] == 1
        entry = data["backups"][0]
        assert entry["genes"] == ["ORPHAN"]
        assert entry["readable"] is True
        assert "size_bytes" in entry

    def test_missing_module_404(self, client, admin_mocks, monkeypatch):
        import med_research.diseases.scaffold as scaf

        def boom(disease_id, target_dir=None):
            raise FileNotFoundError(
                "No disease module 'nope' found. Run 'med-research disease add <id>' first."
            )

        monkeypatch.setattr(scaf, "list_backups", boom)
        resp = client.get("/api/admin/diseases/nope/backups")
        assert resp.status_code == 404
        assert "disease add" in resp.json()["detail"]


# ── Prune ────────────────────────────────────────────────────────────────


class TestAdminPrune:
    def test_preview_is_dry_run_and_writes_nothing(self, client, admin_mocks):
        resp = client.post("/api/admin/diseases/sle/prune", json={"max_genes": 30})
        assert resp.status_code == 200
        data = resp.json()
        assert data["preview"] is True
        assert data["prune"]["genes"] == ["ORPHAN"]
        assert data["merge"]["genes"]["added"] == ["NEWGENE"]
        assert data["prune"]["backup"] is None
        # No writes → no cache invalidation
        assert admin_mocks["cache_clears"] == 0

        call = admin_mocks["prune"][-1]
        assert call["dry_run"] is True
        assert call["prune"] is True
        assert call["max_genes"] == 30
        assert call["use_gwas"] is True and call["use_opentargets"] is True

    def test_apply_writes_and_invalidates_caches(self, client, admin_mocks):
        resp = client.post(
            "/api/admin/diseases/sle/prune",
            json={"apply": True, "skip_reactome": True, "no_cache": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["preview"] is False
        assert data["prune"]["backup"].endswith("pruned_x.json")
        assert admin_mocks["cache_clears"] == 4  # KG + genes + drugs + pathways

        call = admin_mocks["prune"][-1]
        assert call["dry_run"] is False
        assert call["use_reactome"] is False
        assert call["use_cache"] is False
        # API analogue of the CLI confirmation: always-approve callback
        assert callable(call["confirm"])
        assert call["confirm"]({"genes": ["ORPHAN"]}) is True

    def test_unknown_disease_404(self, client, admin_mocks, monkeypatch):
        import med_research.diseases.scaffold as scaf

        def boom(*args, **kwargs):
            raise FileNotFoundError("No disease module 'nope' found.")

        monkeypatch.setattr(scaf, "refresh_disease", boom)
        resp = client.post("/api/admin/diseases/nope/prune", json={})
        assert resp.status_code == 404

    def test_apply_refuses_when_all_sources_failed(self, client, admin_mocks, monkeypatch):
        """No source succeeded → refusing to prune (would flag everything)."""
        import med_research.diseases.scaffold as scaf

        def all_down(*args, **kwargs):
            disease_id = args[0] if args else kwargs.get("disease_id", "sle")
            summary = {
                "disease_id": disease_id,
                "name": "X",
                "efo_id": None,
                "root": "/tmp",
                "dry_run": False,
                "sources": {"opentargets": False, "gwas": False, "reactome": False},
                "merge": {},
                "prune": {},
                "counts": {},
                "files": [],
            }
            return summary

        monkeypatch.setattr(scaf, "refresh_disease", all_down)
        resp = client.post("/api/admin/diseases/sle/prune", json={"apply": True})
        assert resp.status_code == 400
        assert "refusing to prune" in resp.json()["detail"]
        assert admin_mocks["cache_clears"] == 0


# ── Restore ──────────────────────────────────────────────────────────────


class TestAdminRestore:
    def test_preview_resolves_bare_filename_and_writes_nothing(self, client, admin_mocks):
        resp = client.post(
            "/api/admin/diseases/sle/restore",
            json={"backup": "pruned_sle_20260101_000000_000000.json"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["preview"] is True
        assert data["restored"]["genes"] == ["ORPHAN"]
        assert data["updated_pathways"] == ["jak-stat"]
        assert admin_mocks["cache_clears"] == 0

        call = admin_mocks["restore"][-1]
        assert call["dry_run"] is True
        # bare filename resolved via the backups inventory
        assert call["backup_path"].endswith("pruned_sle_20260101_000000_000000.json")
        assert "/tmp/data/backups/" in call["backup_path"]

    def test_apply_with_full_path_invalidates_caches(self, client, admin_mocks):
        resp = client.post(
            "/api/admin/diseases/sle/restore",
            json={"backup": "/tmp/data/backups/pruned_x.json", "apply": True},
        )
        assert resp.status_code == 200
        assert resp.json()["preview"] is False
        assert admin_mocks["cache_clears"] == 4

        call = admin_mocks["restore"][-1]
        assert call["dry_run"] is False
        # Full path passes through untouched (Path-normalized on Windows)
        assert Path(call["backup_path"]) == Path("/tmp/data/backups/pruned_x.json")

    def test_missing_backup_404(self, client, admin_mocks, monkeypatch):
        import med_research.diseases.scaffold as scaf

        def boom(*args, **kwargs):
            raise FileNotFoundError("Backup file not found: nope.json")

        monkeypatch.setattr(scaf, "restore_disease", boom)
        resp = client.post("/api/admin/diseases/sle/restore", json={"backup": "nope.json"})
        assert resp.status_code == 404
        assert "Backup file not found" in resp.json()["detail"]

    def test_omitted_backup_uses_newest_default(self, client, admin_mocks):
        """No backup field → restore_disease resolves the newest backup itself."""
        resp = client.post("/api/admin/diseases/sle/restore", json={})
        assert resp.status_code == 200
        call = admin_mocks["restore"][-1]
        assert call["backup_path"] is None
        assert resp.json()["backup"].endswith("newest.json")

    def test_empty_string_backup_is_rejected(self, client, admin_mocks):
        """A blank backup must not silently mean 'newest'."""
        resp = client.post("/api/admin/diseases/sle/restore", json={"backup": "   "})
        assert resp.status_code == 400
        assert "newest backup" in resp.json()["detail"]
        assert admin_mocks["restore"] == []  # restore never called

    def test_corrupted_backup_400(self, client, admin_mocks, monkeypatch):
        """Unparseable/wrong-shape backup → ValueError → 400."""
        import med_research.diseases.scaffold as scaf

        def bad(*args, **kwargs):
            raise ValueError("Could not parse backup /x/bad.json")

        monkeypatch.setattr(scaf, "restore_disease", bad)
        resp = client.post("/api/admin/diseases/sle/restore", json={"backup": "bad.json"})
        assert resp.status_code == 400
        assert "Could not parse backup" in resp.json()["detail"]


class TestAdminAudit:
    """The audit endpoint surfaces the module's prune/restore history."""

    @staticmethod
    def _canned(monkeypatch, entries):
        import med_research.diseases.audit as audit_mod

        monkeypatch.setattr(
            audit_mod,
            "read_audit",
            lambda disease_id, limit=None, target_dir=None: entries,
        )

    def test_returns_newest_first_with_limit(self, client, monkeypatch):
        canned = [
            {
                "version": 1,
                "ts": "2026-01-01T10:00:00",
                "action": "prune",
                "disease_id": "sle",
                "removed": {"genes": ["OLD"], "drugs": []},
                "backup": "/x/pruned_sle_old.json",
            },
            {
                "version": 1,
                "ts": "2026-01-02T10:00:00",
                "action": "restore",
                "disease_id": "sle",
                "restored": {"genes": ["NEW"], "drugs": []},
                "backup": "/x/pruned_sle_new.json",
            },
        ]
        self._canned(monkeypatch, canned)
        resp = client.get("/api/admin/diseases/sle/audit?limit=1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["disease_id"] == "sle"
        assert body["count"] == 2  # total in the log
        assert len(body["entries"]) == 1
        assert body["entries"][0]["ts"] == "2026-01-02T10:00:00"  # newest
        assert body["entries"][0]["action"] == "restore"

    def test_empty_log_returns_empty_list(self, client, monkeypatch):
        self._canned(monkeypatch, [])
        resp = client.get("/api/admin/diseases/sle/audit")
        assert resp.status_code == 200
        assert resp.json() == {"disease_id": "sle", "count": 0, "entries": []}

    def test_missing_module_404(self, client, monkeypatch):
        import med_research.diseases.audit as audit_mod

        def _boom(disease_id, limit=None, target_dir=None):
            raise FileNotFoundError(f"No disease module '{disease_id}' found.")

        monkeypatch.setattr(audit_mod, "read_audit", _boom)
        resp = client.get("/api/admin/diseases/nope/audit")
        assert resp.status_code == 404
        assert "No disease module" in resp.json()["detail"]

    def test_limit_clamped(self, monkeypatch):
        """Service clamps limit to 1..500 and reports the true total."""
        from med_research.web.services import disease_admin_service

        canned = [
            {
                "version": 1,
                "ts": f"2026-01-01T10:{i:02d}:00",
                "action": "prune",
                "disease_id": "sle",
                "removed": {"genes": [f"G{i}"], "drugs": []},
            }
            for i in range(30)
        ]
        self._canned(monkeypatch, canned)

        out = disease_admin_service.list_disease_audit("sle", limit=10)
        assert out["count"] == 30
        assert len(out["entries"]) == 10
        assert out["entries"][0]["ts"] == "2026-01-01T10:29:00"  # newest first

        assert len(disease_admin_service.list_disease_audit("sle", limit=0)["entries"]) == 1
        assert len(disease_admin_service.list_disease_audit("sle", limit=9999)["entries"]) == 30

    def test_disease_id_sanitized_before_lookup(self, monkeypatch):
        """A path-laden id is cleaned before hitting the module lookup, and the
        response echoes the sanitized id (mirrors list_backups)."""
        import med_research.diseases.audit as audit_mod
        from med_research.web.services import disease_admin_service

        seen = {}

        def spy(disease_id, limit=None, target_dir=None):
            seen["id"] = disease_id
            return []

        monkeypatch.setattr(audit_mod, "read_audit", spy)
        out = disease_admin_service.list_disease_audit("..//zz audit", limit=5)
        assert seen["id"] == "zz_audit"  # sanitized before the filesystem lookup
        assert out["disease_id"] == "zz_audit"
