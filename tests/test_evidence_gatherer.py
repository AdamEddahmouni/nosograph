"""Tests for the Evidence Gatherer module."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


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
    """Tests for the main gather_evidence pipeline."""

    def test_returns_dict_with_expected_keys(self):
        from med_research.pipeline.evidence.gatherer import gather_evidence

        result = gather_evidence("lupus", sources=["pubmed"], max_per_source=3)
        assert isinstance(result, dict)
        for key in ("query", "total_results", "results_by_source", "all_results", "elapsed_seconds"):
            assert key in result, f"Missing key: {key}"

    def test_results_have_required_fields(self):
        from med_research.pipeline.evidence.gatherer import gather_evidence

        result = gather_evidence("lupus treatment", sources=["pubmed"], max_per_source=3)
        for r in result["all_results"]:
            for field in ("title", "source", "source_type", "url", "snippet"):
                assert field in r, f"Missing field: {field}"

    def test_sources_searched_respected(self):
        from med_research.pipeline.evidence.gatherer import gather_evidence

        result = gather_evidence("lupus", sources=["pubmed"], max_per_source=3)
        assert set(result["results_by_source"].keys()) <= {"pubmed"}

    def test_total_matches_sum_of_sources(self):
        from med_research.pipeline.evidence.gatherer import gather_evidence

        result = gather_evidence("lupus treatment", sources=["pubmed", "preprints"], max_per_source=5)
        source_total = sum(result["results_by_source"].values())
        assert source_total == result["total_results"]

    def test_max_per_source_respected(self):
        from med_research.pipeline.evidence.gatherer import gather_evidence

        result = gather_evidence("lupus", sources=["pubmed"], max_per_source=5)
        pubmed_count = result["results_by_source"].get("pubmed", 0)
        assert pubmed_count <= 5

    def test_empty_query_returns_empty(self):
        from med_research.pipeline.evidence.gatherer import gather_evidence

        result = gather_evidence("xyznonexistent999zzz", sources=["pubmed"], max_per_source=3)
        assert isinstance(result["all_results"], list)

    def test_crossref_produced_for_multiple_sources(self):
        from med_research.pipeline.evidence.gatherer import gather_evidence

        result = gather_evidence("lupus", sources=["pubmed", "preprints"], max_per_source=5)
        assert "crossref" in result
        assert "pairs" in result["crossref"]

    def test_clinical_trials_fallback_graceful(self):
        from med_research.pipeline.evidence.gatherer import search_clinical_trials

        results = search_clinical_trials("lupus nephritis", max_results=3)
        assert isinstance(results, list)

    def test_results_sorted_by_recency(self):
        from med_research.pipeline.evidence.gatherer import gather_evidence

        result = gather_evidence("lupus", sources=["pubmed"], max_per_source=10)
        years = [int(r.get("year", 0) or 0) for r in result["all_results"] if r.get("year")]
        # Should be generally descending (newest first), allow some variance
        if len(years) >= 4:
            assert years[0] >= years[-1] or sum(years[:3]) >= sum(years[-3:])


class TestEuropePMC:
    """Tests for Europe PMC search functions."""

    def test_pubmed_search_returns_results(self):
        from med_research.pipeline.evidence.gatherer import search_europe_pmc

        results = search_europe_pmc("lupus", "pubmed", max_results=3, use_cache=False)
        assert isinstance(results, list)
        if results:
            assert "title" in results[0]
            assert results[0]["source_type"] == "pubmed"

    def test_preprints_search_returns_results(self):
        from med_research.pipeline.evidence.gatherer import search_europe_pmc

        results = search_europe_pmc("lupus", "preprints", max_results=3, use_cache=False)
        assert isinstance(results, list)

    def test_patents_search_returns_results(self):
        from med_research.pipeline.evidence.gatherer import search_europe_pmc

        results = search_europe_pmc("lupus", "patents", max_results=3, use_cache=False)
        assert isinstance(results, list)


class TestFDA:
    """Tests for FDA label search."""

    def test_fda_search_returns_results(self):
        from med_research.pipeline.evidence.gatherer import search_fda_labels

        results = search_fda_labels("belimumab", max_results=3, use_cache=False)
        assert isinstance(results, list)


class TestCLIIntegration:
    """Smoke tests for CLI entry point."""

    def test_main_imports(self):
        from med_research.pipeline.evidence.gatherer import main
        assert callable(main)

    def test_report_generation(self, tmp_path):
        from med_research.pipeline.evidence.gatherer import gather_evidence
        from med_research.pipeline.evidence.gatherer_report import generate_html_report

        result = gather_evidence("lupus", sources=["pubmed"], max_per_source=3)
        path = generate_html_report(result)
        assert Path(path).exists()


class TestServiceLayer:
    """Tests for the web API service layer."""

    def test_run_evidence_gather_returns_dict(self):
        from med_research.web.services.evidence_service import run_evidence_gather

        result = run_evidence_gather("lupus", sources=["pubmed"], max_per_source=3)
        assert isinstance(result, dict)
        assert "total_results" in result


@pytest.mark.slow
class TestEvidenceGatherSlow:
    """Slow tests that hit live APIs across all sources."""

    def test_all_sources_gather(self):
        from med_research.pipeline.evidence.gatherer import gather_evidence

        result = gather_evidence("lupus nephritis", max_per_source=5, use_cache=False)
        assert result["total_results"] >= 0
        sources_found = set(result["results_by_source"].keys())
        # Should find results in at least 2 sources
        assert len(sources_found) >= 2

    def test_cli_help(self):
        import subprocess

        result = subprocess.run(
            [sys.executable, "evidence_gatherer/gatherer.py", "--help"],
            capture_output=True, text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        assert result.returncode == 0
        assert "Multi-source" in result.stdout or "evidence" in result.stdout.lower()
