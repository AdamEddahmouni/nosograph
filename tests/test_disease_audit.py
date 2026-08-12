"""Tests for the disease audit log (append-only JSONL per module).

Covers the audit storage primitives (append/read, corrupt-line tolerance,
append-failure non-blocking), the entry builders, and the scaffold-engine
integration: real prune/restore writes record an entry, dry-runs and declined
prunes do not.
"""

import json
from pathlib import Path

import pytest

from med_research.diseases import audit, scaffold

pytestmark = pytest.mark.unit


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_module(tmp_path: Path, disease_id: str = "zzx") -> Path:
    """Create a minimal disease module (no network, no sources)."""
    root = tmp_path / disease_id
    (root / "data").mkdir(parents=True)
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "data" / "profile.json").write_text(
        json.dumps({"id": disease_id, "name": "ZZX"}), encoding="utf-8"
    )
    return root


def _seed_module(root: Path, genes=None, drugs=None, pathways=None) -> None:
    data_dir = root / "data"
    (data_dir / "genes.json").write_text(json.dumps({"genes": genes or []}), encoding="utf-8")
    (data_dir / "drugs.json").write_text(json.dumps({"drugs": drugs or []}), encoding="utf-8")
    (data_dir / "pathways.json").write_text(
        json.dumps({"pathways": pathways or []}), encoding="utf-8"
    )
    (data_dir / "relationships.json").write_text(
        json.dumps({"relationships": []}), encoding="utf-8"
    )


def _fresh_sources():
    """Canned _collect_sources payload: only FRESH is reported by sources."""
    return {
        "efo_id": "EFO_0000000",
        "name": "ZZX Test",
        "description": "",
        "genes": {
            "genes": [{"id": "FRESH", "name": "FRESH", "disease_evidence": "Open Targets x"}]
        },
        "drugs": {"drugs": []},
        "pathways": {"pathways": []},
        "reactome_hits": [],
        "ot_targets": [],
        "gwas_genes": [],
    }


# ── Storage primitives ───────────────────────────────────────────────────


def test_append_and_read_round_trip(tmp_path):
    root = _make_module(tmp_path)
    p1 = audit.append_audit(
        "zzx",
        {"action": "prune", "disease_id": "zzx", "removed": {"genes": ["A"], "drugs": []}},
        target_dir=root,
    )
    p2 = audit.append_audit(
        "zzx",
        {"action": "restore", "disease_id": "zzx", "restored": {"genes": ["A"], "drugs": []}},
        target_dir=root,
    )
    assert p1 == p2 == root / "data" / audit.AUDIT_LOG_NAME
    entries = audit.read_audit("zzx", target_dir=root)
    assert [e["action"] for e in entries] == ["prune", "restore"]  # chronological
    assert entries[0]["version"] == audit.AUDIT_VERSION
    assert entries[0]["ts"]  # auto-added timestamp
    assert entries[0]["removed"] == {"genes": ["A"], "drugs": []}


def test_read_limit_returns_newest(tmp_path):
    root = _make_module(tmp_path)
    for i in range(5):
        audit.append_audit("zzx", {"action": "prune", "disease_id": "zzx", "n": i}, target_dir=root)
    entries = audit.read_audit("zzx", limit=2, target_dir=root)
    assert [e["n"] for e in entries] == [3, 4]


def test_read_missing_module_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        audit.read_audit("nope", target_dir=tmp_path)


def test_read_sanitizes_disease_id(tmp_path):
    """A path-separator-laden id must never resolve outside the diseases dir."""
    root = _make_module(tmp_path, disease_id="zzx")
    audit.append_audit("zzx", {"action": "prune", "disease_id": "zzx"}, target_dir=root)

    # "..//zz x" sanitizes to "zz_x" — a different module id, so the lookup
    # raises instead of walking up to tmp_path (no traversal possible).
    with pytest.raises(FileNotFoundError):
        audit.read_audit("..//zz x", target_dir=tmp_path)

    # The clean id still reads the log (module root as target_dir).
    entries = audit.read_audit("zzx", target_dir=root)
    assert entries[0]["action"] == "prune"


def test_read_no_audit_file_returns_empty(tmp_path):
    root = _make_module(tmp_path)
    assert audit.read_audit("zzx", target_dir=root) == []


def test_corrupt_line_skipped_without_failing(tmp_path):
    root = _make_module(tmp_path)
    log = root / "data" / audit.AUDIT_LOG_NAME
    log.write_text(
        '{"action":"prune","ts":"2026-01-01T00:00:00"}\n'
        "NOT JSON\n"
        '{"action":"restore","ts":"2026-01-02T00:00:00"}\n',
        encoding="utf-8",
    )
    entries = audit.read_audit("zzx", target_dir=root)
    assert [e["action"] for e in entries] == ["prune", "restore"]


def test_append_failure_returns_none(tmp_path, monkeypatch):
    """A failed audit write never raises — the mutation must still succeed."""
    root = _make_module(tmp_path)

    def _broken_open(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(Path, "open", _broken_open)
    assert (
        audit.append_audit("zzx", {"action": "prune", "disease_id": "zzx"}, target_dir=root) is None
    )


# ── Entry builders ───────────────────────────────────────────────────────


def test_prune_entry_maps_summary():
    summary = {
        "disease_id": "sle",
        "name": "SLE",
        "prune": {
            "enabled": True,
            "aborted": False,
            "genes": ["ORPHAN"],
            "drugs": ["D2"],
            "scrubbed_pathways": ["jak-stat"],
            "backup": "/x/pruned_sle.json",
        },
        "merge": {
            "genes": {"added": ["N1"], "updated": [], "kept": ["K1"]},
            "drugs": {"added": [], "updated": [], "kept": []},
            "pathways": {"added": [], "updated": [], "kept": []},
        },
        "counts": {"genes": 5, "drugs": 2, "pathways": 3, "relationships": 9},
    }
    e = audit.prune_entry(summary)
    assert e["action"] == "prune"
    assert e["disease_id"] == "sle" and e["name"] == "SLE"
    assert e["removed"] == {"genes": ["ORPHAN"], "drugs": ["D2"]}
    assert e["scrubbed_pathways"] == ["jak-stat"]
    assert e["backup"] == "/x/pruned_sle.json"
    assert e["merge"]["genes"] == {"added": 1, "updated": 0, "kept": 1}
    assert e["counts"]["genes"] == 5


def test_restore_entry_maps_summary():
    summary = {
        "disease_id": "sle",
        "backup": "/x/pruned_sle.json",
        "backup_disease_id": "sle",
        "restored": {"genes": ["ORPHAN"], "drugs": []},
        "skipped": {"genes": [], "drugs": ["D2"]},
        "updated_pathways": ["jak-stat"],
        "counts": {"genes": 6, "drugs": 2, "pathways": 3, "relationships": 11},
    }
    e = audit.restore_entry(summary)
    assert e["action"] == "restore"
    assert e["restored"] == {"genes": ["ORPHAN"], "drugs": []}
    assert e["skipped"] == {"genes": [], "drugs": ["D2"]}
    assert e["updated_pathways"] == ["jak-stat"]
    assert e["backup"] == "/x/pruned_sle.json"
    assert e["backup_disease_id"] == "sle"


# ── Engine integration (scaffold records on real writes) ────────────────


def test_refresh_prune_records_audit_but_dry_run_and_decline_do_not(tmp_path, monkeypatch):
    root = _make_module(tmp_path)
    _seed_module(root, genes=[{"id": "ORPHAN", "category": "Curated legacy"}])
    monkeypatch.setattr(scaffold, "_collect_sources", lambda **kw: _fresh_sources())

    # Dry run: no audit file
    scaffold.refresh_disease("zzx", target_dir=root, prune=True, dry_run=True)
    assert not (root / "data" / audit.AUDIT_LOG_NAME).exists()

    # Declined prune: nothing written, no audit entry
    scaffold.refresh_disease("zzx", target_dir=root, prune=True, confirm=lambda plan: False)
    assert not (root / "data" / audit.AUDIT_LOG_NAME).exists()

    # Real apply: audit entry records the removal + backup path
    summary = scaffold.refresh_disease("zzx", target_dir=root, prune=True)
    assert "ORPHAN" in summary["prune"]["genes"]
    entries = audit.read_audit("zzx", target_dir=root)
    assert len(entries) == 1
    e = entries[0]
    assert e["action"] == "prune"
    assert e["removed"] == {"genes": ["ORPHAN"], "drugs": []}
    assert e["backup"] and Path(e["backup"]).exists()
    assert e["merge"]["genes"] == {"added": 1, "updated": 0, "kept": 0}


def test_refresh_prune_with_nothing_to_remove_still_records(tmp_path, monkeypatch):
    """A prune run that writes files but removes nothing is still traceable."""
    root = _make_module(tmp_path)
    _seed_module(root, genes=[{"id": "FRESH"}])  # FRESH is re-reported → no candidates
    monkeypatch.setattr(scaffold, "_collect_sources", lambda **kw: _fresh_sources())

    scaffold.refresh_disease("zzx", target_dir=root, prune=True)
    entries = audit.read_audit("zzx", target_dir=root)
    assert len(entries) == 1
    assert entries[0]["action"] == "prune"
    assert entries[0]["removed"] == {"genes": [], "drugs": []}
    assert entries[0]["backup"] is None


def test_restore_records_audit_but_dry_run_does_not(tmp_path):
    root = _make_module(tmp_path)
    _seed_module(
        root,
        genes=[{"id": "FRESH"}],
        pathways=[
            {
                "id": "jak-stat",
                "name": "JAK-STAT Signaling",
                "key_components": [],
                "therapeutic_targets": [],
            }
        ],
    )
    backup_dir = root / "data" / "backups"
    backup_dir.mkdir(parents=True)
    backup_path = backup_dir / "pruned_zzx_20260101_000000_000000.json"
    backup_path.write_text(
        json.dumps(
            {
                "disease_id": "zzx",
                "pruned_at": "2026-01-01T00:00:00",
                "genes": [{"id": "ORPHAN", "category": "Curated legacy"}],
                "drugs": [],
                "pathway_memberships": {"ORPHAN": ["jak-stat"]},
            }
        ),
        encoding="utf-8",
    )

    # Dry run first: nothing recorded
    scaffold.restore_disease("zzx", backup_path=backup_path, target_dir=root, dry_run=True)
    assert not (root / "data" / audit.AUDIT_LOG_NAME).exists()

    # Real restore: entry records what came back and from which backup
    summary = scaffold.restore_disease("zzx", backup_path=backup_path, target_dir=root)
    assert summary["restored"] == {"genes": ["ORPHAN"], "drugs": []}
    entries = audit.read_audit("zzx", target_dir=root)
    assert len(entries) == 1
    e = entries[0]
    assert e["action"] == "restore"
    assert e["restored"] == {"genes": ["ORPHAN"], "drugs": []}
    assert e["skipped"] == {"genes": [], "drugs": []}
    assert e["updated_pathways"] == ["jak-stat"]
    assert e["backup"] == str(backup_path)
