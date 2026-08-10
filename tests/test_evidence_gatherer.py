"""Tests for the Evidence Gatherer module."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestCoverageGating:
    """Blocked status when curated disease inputs are missing."""

    def test_blocked_when_pubmed_queries_missing(self, monkeypatch):
        from med_research.diseases.base import Disease
        from med_research.pipeline.evidence.gatherer import gather_evidence

        monkeypatch.setattr(Disease, "config", property(lambda self: {}))
        result = gather_evidence(
            "rheumatoid arthritis treatment",
            sources=["pubmed"],
            max_per_source=3,
            disease_id="ra",
        )
        assert result["status"] == "blocked"
        assert result["total_results"] == 0
        assert result["coverage"]["module"] == "evidence_gather"
        assert "pubmed_queries" in result["coverage"]["missing_inputs"]


class TestCacheFunctions:
    """Tests for cache loading and saving."""

    def test_cache_key_generation(self):
        from med_research.pipeline.evidence.gatherer import _cache_key

        key = _cache_key("lupus", "pubmed", 20)
        assert "lupus" in key
        assert "pubmed" in key
        assert "20" in key

    def test_cache_key_is_unique_per_source(self):
        from med_research.pipeline.evidence.gatherer import _cache_key

        k1 = _cache_key("lupus", "pubmed", 20)
        k2 = _cache_key("lupus", "preprints", 20)
        assert k1 != k2


class TestGatherEvidence:
    """Tests for the main gather_evidence pipeline (mocked HTTP)."""

    def test_returns_dict_with_expected_keys(self, evidence_http_mocks):
        from med_research.pipeline.evidence.gatherer import gather_evidence

        result = gather_evidence(
            "lupus",
            sources=["pubmed"],
            max_per_source=3,
            use_cache=False,
        )
        assert isinstance(result, dict)
        for key in ("query", "total_results", "results_by_source", "all_results", "elapsed_seconds"):
            assert key in result, f"Missing key: {key}"

    def test_results_have_required_fields(self, evidence_http_mocks):
        from med_research.pipeline.evidence.gatherer import gather_evidence

        result = gather_evidence(
            "lupus treatment",
            sources=["pubmed"],
            max_per_source=3,
            use_cache=False,
        )
        assert result["all_results"]
        for r in result["all_results"]:
            for field in ("title", "source", "source_type", "url", "snippet"):
                assert field in r, f"Missing field: {field}"

    def test_sources_searched_respected(self, evidence_http_mocks):
        from med_research.pipeline.evidence.gatherer import gather_evidence

        result = gather_evidence(
            "lupus",
            sources=["pubmed"],
            max_per_source=3,
            use_cache=False,
        )
        assert set(result["results_by_source"].keys()) <= {"pubmed"}

    def test_total_matches_sum_of_sources(self, evidence_http_mocks):
        from med_research.pipeline.evidence.gatherer import gather_evidence

        result = gather_evidence(
            "lupus treatment",
            sources=["pubmed", "preprints"],
            max_per_source=5,
            use_cache=False,
        )
        source_total = sum(result["results_by_source"].values())
        assert source_total == result["total_results"]

    def test_max_per_source_respected(self, evidence_http_mocks):
        from med_research.pipeline.evidence.gatherer import gather_evidence

        result = gather_evidence(
            "lupus",
            sources=["pubmed"],
            max_per_source=1,
            use_cache=False,
        )
        pubmed_count = result["results_by_source"].get("pubmed", 0)
        assert pubmed_count <= 1

    def test_empty_query_returns_empty(self, evidence_http_mocks):
        from med_research.pipeline.evidence.gatherer import gather_evidence

        result = gather_evidence(
            "xyznonexistent999zzz",
            sources=["pubmed"],
            max_per_source=3,
            use_cache=False,
        )
        assert isinstance(result["all_results"], list)

    def test_crossref_produced_for_multiple_sources(self, evidence_http_mocks):
        from med_research.pipeline.evidence.gatherer import gather_evidence

        result = gather_evidence(
            "lupus",
            sources=["pubmed", "preprints"],
            max_per_source=5,
            use_cache=False,
        )
        assert "crossref" in result
        assert "pairs" in result["crossref"]

    def test_clinical_trials_fallback_graceful(self):
        from med_research.pipeline.evidence.gatherer import search_clinical_trials

        results = search_clinical_trials("lupus nephritis", max_results=3)
        assert isinstance(results, list)

    def test_results_sorted_by_recency(self, evidence_http_mocks):
        from med_research.pipeline.evidence.gatherer import gather_evidence

        result = gather_evidence(
            "lupus",
            sources=["pubmed"],
            max_per_source=10,
            use_cache=False,
        )
        years = [int(r.get("year", 0) or 0) for r in result["all_results"] if r.get("year")]
        assert years
        assert all(year >= 2020 for year in years)


class TestEuropePMC:
    """Tests for Europe PMC search functions (mocked HTTP)."""

    def test_pubmed_search_returns_results(self, evidence_http_mocks):
        from med_research.pipeline.evidence.gatherer import search_europe_pmc

        results = search_europe_pmc("lupus", "pubmed", max_results=3, use_cache=False)
        assert isinstance(results, list)
        assert results
        assert "title" in results[0]
        assert results[0]["source_type"] == "pubmed"

    def test_preprints_search_returns_results(self, evidence_http_mocks):
        from med_research.pipeline.evidence.gatherer import search_europe_pmc

        results = search_europe_pmc("lupus", "preprints", max_results=3, use_cache=False)
        assert isinstance(results, list)
        assert results

    def test_patents_search_returns_results(self, evidence_http_mocks):
        from med_research.pipeline.evidence.gatherer import search_europe_pmc

        results = search_europe_pmc("lupus", "patents", max_results=3, use_cache=False)
        assert isinstance(results, list)
        assert results


class TestFDA:
    """Tests for FDA label search (mocked HTTP)."""

    def test_fda_search_returns_results(self, evidence_http_mocks):
        from med_research.pipeline.evidence.gatherer import search_fda_labels

        results = search_fda_labels("belimumab", max_results=3, use_cache=False)
        assert isinstance(results, list)
        assert results
        assert results[0]["source_type"] == "fda_labels"


class TestCLIIntegration:
    """Smoke tests for CLI entry point."""

    def test_main_imports(self):
        from med_research.pipeline.evidence.gatherer import main

        assert callable(main)

    def test_report_generation(self, evidence_http_mocks, tmp_path):
        from med_research.pipeline.evidence.gatherer import gather_evidence
        from med_research.pipeline.evidence.gatherer_report import generate_html_report
        from med_research.pipeline.provenance import build_provenance

        result = gather_evidence(
            "lupus",
            sources=["pubmed"],
            max_per_source=3,
            use_cache=False,
        )
        provenance = build_provenance(
            disease_id="sle",
            module="evidence_gather",
            sources=["pubmed"],
            query="lupus",
            cache_or_live="cache",
        )
        path = generate_html_report(result, provenance=provenance)
        assert Path(path).exists()
        html = Path(path).read_text(encoding="utf-8")
        assert "Reproducibility" in html


class TestServiceLayer:
    """Tests for the web API service layer."""

    def test_run_evidence_gather_returns_dict(self, evidence_http_mocks):
        from med_research.web.services.evidence_service import run_evidence_gather

        result = run_evidence_gather(
            "lupus",
            sources=["pubmed"],
            max_per_source=3,
            use_cache=False,
        )
        assert isinstance(result, dict)
        assert "total_results" in result


class TestEvidenceGatherSlow:
    """Slow tests that hit live APIs across all sources."""

    @pytest.mark.slow
    def test_all_sources_gather(self):
        from med_research.pipeline.evidence.gatherer import gather_evidence

        result = gather_evidence("lupus nephritis", max_per_source=5, use_cache=False)
        assert result["total_results"] >= 0
        sources_found = set(result["results_by_source"].keys())
        assert len(sources_found) >= 2

    @pytest.mark.slow
    def test_live_pubmed_search(self):
        from med_research.pipeline.evidence.gatherer import search_europe_pmc

        results = search_europe_pmc("lupus nephritis", "pubmed", max_results=3, use_cache=False)
        assert isinstance(results, list)
        if results:
            assert "title" in results[0]

    def test_cli_help(self):
        from tests.cli_helpers import cli_help_output

        help_text = cli_help_output("evidence", "--help")
        assert "evidence" in help_text.lower()
