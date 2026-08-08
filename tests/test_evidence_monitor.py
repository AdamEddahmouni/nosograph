"""
Tests for the Evidence Monitor module.

Covers: snapshot hashing, diff engine, alert generation, snapshot listing,
and report generation.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from med_research.pipeline.evidence.monitor import (
    _entity_query_suffix,
    _find_new_items,
    _hash_results,
    _tracked_queries,
    compare_snapshots,
    list_snapshots,
    load_json,
    load_latest_snapshots,
    save_json,
    take_snapshot,
)
from med_research.pipeline.evidence.monitor_report import generate_html_report

# ── Sample data ───────────────────────────────────────────────────────────

SAMPLE_RESULTS_A = [
    {"id": "P1", "title": "Paper One", "source_type": "pubmed", "year": "2024", "url": ""},
    {"id": "P2", "title": "Paper Two", "source_type": "pubmed", "year": "2023", "url": ""},
]

SAMPLE_RESULTS_B = [
    {"id": "P1", "title": "Paper One", "source_type": "pubmed", "year": "2024", "url": ""},
    {"id": "P2", "title": "Paper Two", "source_type": "pubmed", "year": "2023", "url": ""},
    {"id": "P3", "title": "Paper Three (NEW)", "source_type": "preprints", "year": "2025", "url": ""},
]

SAMPLE_SNAPSHOT_PREV = {
    "snapshot_id": "20250101_120000",
    "timestamp": "2025-01-01T12:00:00",
    "tracked_queries": ["lupus treatment"],
    "tracked_drugs": ["Rituximab"],
    "tracked_genes": ["BTK"],
    "sources": ["pubmed"],
    "queries": {
        "lupus treatment": {"results": SAMPLE_RESULTS_A, "total": 2,
                            "hash": _hash_results(SAMPLE_RESULTS_A)},
    },
    "drugs": {
        "Rituximab": {"results": SAMPLE_RESULTS_A, "total": 2,
                      "hash": _hash_results(SAMPLE_RESULTS_A)},
    },
    "genes": {
        "BTK": {"results": SAMPLE_RESULTS_A, "total": 2,
                "hash": _hash_results(SAMPLE_RESULTS_A)},
    },
}

SAMPLE_SNAPSHOT_CURR = {
    "snapshot_id": "20250102_120000",
    "timestamp": "2025-01-02T12:00:00",
    "tracked_queries": ["lupus treatment"],
    "tracked_drugs": ["Rituximab"],
    "tracked_genes": ["BTK"],
    "sources": ["pubmed"],
    "queries": {
        "lupus treatment": {"results": SAMPLE_RESULTS_B, "total": 3,
                            "hash": _hash_results(SAMPLE_RESULTS_B)},
    },
    "drugs": {
        "Rituximab": {"results": SAMPLE_RESULTS_B, "total": 3,
                      "hash": _hash_results(SAMPLE_RESULTS_B)},
    },
    "genes": {
        "BTK": {"results": SAMPLE_RESULTS_B, "total": 3,
                "hash": _hash_results(SAMPLE_RESULTS_B)},
    },
}


# ── Disease Scoping Tests ─────────────────────────────────────────────────


class TestDiseaseScoping:
    def test_sle_keeps_legacy_tracked_queries(self):
        """SLE retains the original hardcoded monitor query list."""
        queries = _tracked_queries("sle")
        assert "B cell depletion therapy lupus" in queries
        assert "belimumab lupus" in queries

    def test_ra_uses_configured_pubmed_queries(self):
        """Non-SLE diseases use curated PUBMED_QUERIES from config."""
        queries = _tracked_queries("ra")
        assert queries
        assert all("lupus" not in query.lower() for query in queries)
        assert any("ra" in query.lower() for query in queries)

    def test_entity_query_suffix_for_sle(self):
        assert _entity_query_suffix("sle") == "lupus"

    def test_entity_query_suffix_for_ra(self):
        suffix = _entity_query_suffix("ra")
        assert "lupus" not in suffix
        assert "rheumatoid" in suffix


class TestCoverageGating:
    def test_blocked_when_pubmed_queries_missing(self, monkeypatch):
        from med_research.diseases.base import Disease

        monkeypatch.setattr(Disease, "config", property(lambda self: {}))
        result = take_snapshot(disease_id="ra")
        assert result["status"] == "blocked"
        assert result["coverage"]["module"] == "evidence_monitor"
        assert "pubmed_queries" in result["coverage"]["missing_inputs"]

    def test_snapshot_uses_disease_scoped_drug_queries(self, monkeypatch):
        """Drug snapshot queries should not hardcode lupus for RA."""
        captured_queries: list[str] = []

        def _fake_gather(query, **kwargs):
            captured_queries.append(query)
            return {"all_results": [], "total_results": 0}

        monkeypatch.setattr(
            "med_research.pipeline.evidence.monitor.gather_evidence",
            _fake_gather,
        )
        monkeypatch.setattr(
            "med_research.pipeline.evidence.monitor._load_tracked_entities",
            lambda: (["Methotrexate"], []),
        )
        monkeypatch.setattr(
            "med_research.pipeline.evidence.monitor._tracked_queries",
            lambda disease_id="sle": ["ra treatment"],
        )
        take_snapshot(disease_id="ra", sources=["pubmed"], max_per_query=1)
        assert captured_queries
        assert all("lupus" not in query.lower() for query in captured_queries)
        assert any("methotrexate" in query.lower() for query in captured_queries)


# ── Hashing Tests ─────────────────────────────────────────────────────────


class TestHashResults:
    def test_identical_results_same_hash(self):
        """Identical results produce identical hashes."""
        h1 = _hash_results(SAMPLE_RESULTS_A)
        h2 = _hash_results(SAMPLE_RESULTS_A)
        assert h1 == h2

    def test_different_results_different_hash(self):
        """Different results produce different hashes."""
        h1 = _hash_results(SAMPLE_RESULTS_A)
        h2 = _hash_results(SAMPLE_RESULTS_B)
        assert h1 != h2

    def test_empty_list_hashes(self):
        """Empty list produces a hash."""
        h = _hash_results([])
        assert isinstance(h, str)
        assert len(h) == 16

    def test_hash_is_stable(self):
        """Hash is stable across repeated calls."""
        h1 = _hash_results(SAMPLE_RESULTS_A)
        h2 = _hash_results(SAMPLE_RESULTS_A)
        assert h1 == h2


# ── Find New Items Tests ────────────────────────────────────────────────


class TestFindNewItems:
    def test_finds_new_item(self):
        """Detects a new item in current results."""
        new = _find_new_items(SAMPLE_RESULTS_A, SAMPLE_RESULTS_B)
        assert len(new) == 1
        assert new[0]["title"] == "Paper Three (NEW)"

    def test_no_new_items(self):
        """Returns empty list when no new items."""
        new = _find_new_items(SAMPLE_RESULTS_A, SAMPLE_RESULTS_A)
        assert new == []

    def test_empty_prev_all_new(self):
        """All items are new when previous is empty."""
        new = _find_new_items([], SAMPLE_RESULTS_A)
        assert len(new) == 2

    def test_empty_curr_no_new(self):
        """No new items when current is empty."""
        new = _find_new_items(SAMPLE_RESULTS_A, [])
        assert new == []

    def test_items_without_ids(self):
        """Items without IDs use titles for comparison."""
        results = [
            {"title": "Title A", "year": "2024"},
            {"title": "Title B", "year": "2024"},
        ]
        prev = [{"title": "Title A", "year": "2024"}]
        new = _find_new_items(prev, results)
        assert len(new) == 1
        assert new[0]["title"] == "Title B"


# ── Compare Snapshots Tests ───────────────────────────────────────────────


class TestCompareSnapshots:
    def test_detects_changed_queries(self):
        """Detects changed queries between snapshots."""
        diff = compare_snapshots(SAMPLE_SNAPSHOT_PREV, SAMPLE_SNAPSHOT_CURR)
        assert "lupus treatment" in diff["changes"]["changed_queries"]

    def test_detects_changed_drugs(self):
        """Detects changed drugs between snapshots."""
        diff = compare_snapshots(SAMPLE_SNAPSHOT_PREV, SAMPLE_SNAPSHOT_CURR)
        assert "Rituximab" in diff["changes"]["changed_drugs"]

    def test_detects_changed_genes(self):
        """Detects changed genes between snapshots."""
        diff = compare_snapshots(SAMPLE_SNAPSHOT_PREV, SAMPLE_SNAPSHOT_CURR)
        assert "BTK" in diff["changes"]["changed_genes"]

    def test_generates_alerts_for_changes(self):
        """Generates alerts for detected changes."""
        diff = compare_snapshots(SAMPLE_SNAPSHOT_PREV, SAMPLE_SNAPSHOT_CURR)
        assert len(diff["alerts"]) == 3  # query + drug + gene

    def test_no_changes_no_alerts(self):
        """Same snapshots produce no changes and no alerts."""
        diff = compare_snapshots(SAMPLE_SNAPSHOT_PREV, SAMPLE_SNAPSHOT_PREV)
        assert diff["total_changes"] == 0
        assert diff["alerts"] == []

    def test_elapsed_hours_correct(self):
        """Correctly computes elapsed hours."""
        diff = compare_snapshots(SAMPLE_SNAPSHOT_PREV, SAMPLE_SNAPSHOT_CURR)
        assert diff["hours_elapsed"] == 24.0

    def test_new_drug_detected(self):
        """Detects drugs in current snapshot not in previous."""
        prev = {**SAMPLE_SNAPSHOT_PREV, "drugs": {}}
        diff = compare_snapshots(prev, SAMPLE_SNAPSHOT_CURR)
        assert "Rituximab" in diff["changes"]["new_drugs"]


# ── Snapshot Listing Tests ────────────────────────────────────────────────


class TestSnapshotListing:
    def test_list_snapshots_returns_list(self):
        """list_snapshots returns a list."""
        snapshots = list_snapshots()
        assert isinstance(snapshots, list)

    def test_load_latest_returns_list(self):
        """load_latest_snapshots returns a list."""
        snapshots = load_latest_snapshots(2)
        assert isinstance(snapshots, list)
        assert len(snapshots) <= 2


# ── JSON Helpers ──────────────────────────────────────────────────────────


class TestJSONHelpers:
    def test_save_and_load_roundtrip(self, tmp_path):
        """JSON save/load roundtrip works."""
        path = tmp_path / "test.json"
        data = {"key": "value"}
        save_json(path, data)
        loaded = load_json(path)
        assert loaded == data


# ── Report Generation ─────────────────────────────────────────────────────


class TestReportGeneration:
    def test_generates_html_report(self):
        """Report generation creates valid HTML."""
        with patch.object(Path, "write_text") as mock_write:
            generate_html_report(
                compare_snapshots(SAMPLE_SNAPSHOT_PREV, SAMPLE_SNAPSHOT_CURR),
                SAMPLE_SNAPSHOT_PREV,
                SAMPLE_SNAPSHOT_CURR,
            )
            mock_write.assert_called_once()
            html = mock_write.call_args[0][0]
            assert "Evidence Monitor" in html
            assert "Alerts" in html
            assert "Paper Three" in html


# ── Slow / Integration Tests ──────────────────────────────────────────────


@pytest.mark.slow
class TestMonitorIntegration:
    def test_snapshot_and_diff_workflow(self):
        """Full snapshot + diff workflow runs end to end."""
        from med_research.pipeline.evidence.monitor import run_diff

        result = run_diff()
        assert "snapshot_id" in result or "prev_snapshot" in result
