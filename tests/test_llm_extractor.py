"""
Tests for the LLM Evidence Extractor module.

Covers: cache key generation, JSON response cleaning, structured extraction
(no-API mode), statistics computation, and report generation.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Imports ───────────────────────────────────────────────────────────────


from med_research.pipeline.evidence.extractor import (
    _cache_key,
    _clean_json_response,
    _compute_extraction_stats,
    extract_all,
    extract_evidence,
)
from med_research.pipeline.evidence.extractor_report import generate_html_report

# ── Helpers ───────────────────────────────────────────────────────────────


SAMPLE_EXTRACTIONS = [
    {
        "title": "Rituximab in refractory SLE: a multicenter RCT",
        "source_type": "pubmed",
        "source": "N Engl J Med",
        "year": "2023",
        "url": "https://example.com/1",
        "id": "PMID12345",
        "evidence_level": "rct",
        "model_system": "human",
        "key_findings": "Rituximab plus standard therapy showed significant improvement in renal outcomes.",
        "drugs_mentioned": ["Rituximab", "Mycophenolate"],
        "disease": "Systemic Lupus Erythematosus",
        "study_design": "double_blind_rct",
        "sample_size": 144,
        "p_value": "0.002",
        "effect_size": "HR=0.68",
        "relevance_to_query": 95,
        "confidence": 92,
    },
    {
        "title": "Mouse model of lupus nephritis treated with BTK inhibitor",
        "source_type": "preprints",
        "source": "bioRxiv",
        "year": "2024",
        "url": "https://example.com/2",
        "id": "PPR67890",
        "evidence_level": "preclinical_in_vivo",
        "model_system": "murine",
        "key_findings": "BTK inhibition reduced proteinuria and autoantibody titers in MRL/lpr mice.",
        "drugs_mentioned": ["Fenebrutinib"],
        "disease": "Lupus Nephritis",
        "study_design": "preclinical",
        "sample_size": 24,
        "p_value": "0.01",
        "effect_size": None,
        "relevance_to_query": 88,
        "confidence": 85,
    },
    {
        "title": "In vitro screening of JAK inhibitors in SLE PBMCs",
        "source_type": "pubmed",
        "source": "Arthritis Rheumatol",
        "year": "2022",
        "url": "https://example.com/3",
        "id": "PMID11111",
        "evidence_level": "preclinical_in_vitro",
        "model_system": "in_vitro",
        "key_findings": "Tofacitinib and baricitinib suppressed IFN-α signaling in SLE PBMCs.",
        "drugs_mentioned": ["Tofacitinib", "Baricitinib"],
        "disease": "Systemic Lupus Erythematosus",
        "study_design": "in_vitro",
        "sample_size": None,
        "p_value": "0.001",
        "effect_size": None,
        "relevance_to_query": 82,
        "confidence": 78,
    },
    {
        "title": "Case report: belimumab-induced remission in refractory SLE",
        "source_type": "pubmed",
        "source": "Lupus",
        "year": "2023",
        "url": "https://example.com/4",
        "id": "PMID22222",
        "evidence_level": "case_report",
        "model_system": "human",
        "key_findings": "Single patient achieved complete remission after 6 months of belimumab.",
        "drugs_mentioned": ["Belimumab"],
        "disease": "Systemic Lupus Erythematosus",
        "study_design": "case_report",
        "sample_size": 1,
        "p_value": None,
        "effect_size": None,
        "relevance_to_query": 70,
        "confidence": 65,
    },
]

pytestmark = pytest.mark.unit



# ── Cache Key Tests ───────────────────────────────────────────────────────


class TestCacheKey:
    def test_consistent_key(self):
        """Same inputs produce same cache key."""
        k1 = _cache_key("PMID12345", "gpt-4o-mini")
        k2 = _cache_key("PMID12345", "gpt-4o-mini")
        assert k1 == k2

    def test_different_ids_different_keys(self):
        """Different article IDs produce different keys."""
        k1 = _cache_key("PMID12345", "gpt-4o-mini")
        k2 = _cache_key("PMID67890", "gpt-4o-mini")
        assert k1 != k2

    def test_different_models_different_keys(self):
        """Different models produce different keys."""
        k1 = _cache_key("PMID12345", "gpt-4o-mini")
        k2 = _cache_key("PMID12345", "gpt-4")
        assert k1 != k2

    def test_includes_model_in_key(self):
        """Model name is reflected in cache key."""
        k1 = _cache_key("PMID12345", "gpt-4o-mini")
        assert "gpt-4o-mini" in k1
        assert "PMID12345" in k1


# ── JSON Cleaning Tests ───────────────────────────────────────────────────


class TestCleanJSONResponse:
    def test_clean_plain_json(self):
        """Plain JSON is returned unchanged."""
        text = '{"key": "value"}'
        assert _clean_json_response(text) == '{"key": "value"}'

    def test_clean_markdown_fence(self):
        """Markdown code fence is stripped."""
        text = '```json\n{"key": "value"}\n```'
        assert _clean_json_response(text) == '{"key": "value"}'

    def test_clean_markdown_no_lang(self):
        """Markdown fence without language tag."""
        text = '```\n{"key": "value"}\n```'
        assert _clean_json_response(text) == '{"key": "value"}'

    def test_clean_extracts_json_from_text(self):
        """Extracts JSON object from surrounding text."""
        text = 'Here is the result: {"key": "value"} and more text'
        assert _clean_json_response(text) == '{"key": "value"}'

    def test_clean_no_braces(self):
        """Returns original text if no braces found."""
        text = "No JSON here"
        assert _clean_json_response(text) == "No JSON here"


# ── Statistics Tests ─────────────────────────────────────────────────────


class TestComputeExtractionStats:
    def test_empty_list(self):
        """Empty extractions returns empty stats."""
        assert _compute_extraction_stats([]) == {}

    def test_evidence_level_distribution(self):
        """Correctly counts evidence levels."""
        stats = _compute_extraction_stats(SAMPLE_EXTRACTIONS)
        levels = stats["evidence_levels"]
        assert levels.get("rct") == 1
        assert levels.get("preclinical_in_vivo") == 1
        assert levels.get("preclinical_in_vitro") == 1
        assert levels.get("case_report") == 1

    def test_model_system_distribution(self):
        """Correctly counts model systems."""
        stats = _compute_extraction_stats(SAMPLE_EXTRACTIONS)
        systems = stats["model_systems"]
        assert systems.get("human") == 2
        assert systems.get("murine") == 1
        assert systems.get("in_vitro") == 1

    def test_unique_drugs(self):
        """Correctly collects unique drug mentions (6 across 4 articles)."""
        stats = _compute_extraction_stats(SAMPLE_EXTRACTIONS)
        assert stats["n_unique_drugs"] == 6
        assert "Rituximab" in stats["unique_drugs_mentioned"]
        assert "Fenebrutinib" in stats["unique_drugs_mentioned"]
        assert "Belimumab" in stats["unique_drugs_mentioned"]

    def test_avg_sample_size(self):
        """Correctly computes average sample size."""
        stats = _compute_extraction_stats(SAMPLE_EXTRACTIONS)
        # (144 + 24 + 1) / 3 = 56.33 → 56
        assert stats["avg_sample_size"] == 56
        assert stats["articles_with_sample_size"] == 3

    def test_avg_confidence_and_relevance(self):
        """Correctly computes averages."""
        stats = _compute_extraction_stats(SAMPLE_EXTRACTIONS)
        # (92 + 85 + 78 + 65) / 4 = 80.0
        assert stats["avg_confidence"] == 80.0
        # (95 + 88 + 82 + 70) / 4 = 83.75 → 83.8
        assert stats["avg_relevance"] == 83.8


# ── Report Generation Tests ───────────────────────────────────────────────


class TestReportGeneration:
    def test_generates_html_file(self, tmp_path):
        """Report generation creates a valid HTML file."""
        results = {
            "query": "lupus treatment",
            "model": "gpt-4o-mini",
            "total_extracted": 4,
            "successful_extractions": 4,
            "elapsed_seconds": 3.5,
            "extractions": SAMPLE_EXTRACTIONS,
            "stats": _compute_extraction_stats(SAMPLE_EXTRACTIONS),
        }

        with patch.object(Path, "write_text") as mock_write:
            generate_html_report(results)
            mock_write.assert_called_once()
            # Verify it contains key sections
            html = mock_write.call_args[0][0]
            assert "LLM Evidence Extraction" in html
            assert "lupus treatment" in html
            assert "Evidence Level Distribution" in html
            assert "Model System Distribution" in html
            assert "Rituximab" in html

    def test_empty_extractions_report(self, tmp_path):
        """Report handles empty extractions gracefully."""
        results = {
            "query": "test",
            "model": "gpt-4o-mini",
            "total_extracted": 0,
            "successful_extractions": 0,
            "elapsed_seconds": 0.0,
            "extractions": [],
            "stats": {},
        }

        with patch.object(Path, "write_text") as mock_write:
            generate_html_report(results)
            html = mock_write.call_args[0][0]
            assert "0" in html  # total_extracted
            assert "No data" in html


# ── Extraction (No-API Mode) Tests ───────────────────────────────────────


class TestExtractEvidenceNoAPI:
    @pytest.fixture(autouse=True)
    def _isolate_cache(self, tmp_path, monkeypatch):
        """Write to a temp cache instead of the tracked pipeline data dir."""
        monkeypatch.setattr("med_research.pipeline.evidence.extractor.DATA_DIR", tmp_path)
        monkeypatch.setattr(
            "med_research.pipeline.evidence.extractor.CACHE_PATH",
            tmp_path / "extraction_cache.json",
        )

    def test_extract_without_api_key(self):
        """Extraction without API key returns minimal dict."""
        article = {
            "title": "Test Article",
            "source": "Test Journal",
            "source_type": "pubmed",
            "year": "2024",
            "snippet": "Test abstract",
            "id": "TEST001",
        }
        # Ensure no API key is set
        with patch("med_research.pipeline.evidence.extractor.API_KEY", ""):
            result = extract_evidence(article, "test query", use_cache=False)
            assert result is not None
            assert result["evidence_level"] == "unknown"
            assert result["confidence"] == 0

    def test_extract_with_api_key_but_failed_call(self):
        """Extraction with API key but failed network returns defaults."""
        article = {
            "title": "Test Article",
            "source": "Test Journal",
            "source_type": "pubmed",
            "year": "2024",
            "snippet": "Test abstract",
            "id": "TEST001",
        }
        with (
            patch("med_research.pipeline.evidence.extractor.API_KEY", "fake-key"),
            patch("med_research.pipeline.evidence.extractor.call_llm", return_value=None),
        ):
            result = extract_evidence(article, "test query", use_cache=False)
            assert result is not None
            assert result["evidence_level"] == "unknown"
            assert result["confidence"] == 0

    def test_extract_with_malformed_llm_response(self):
        """Handles malformed LLM JSON response gracefully."""
        article = {
            "title": "Test Article",
            "source": "Test Journal",
            "source_type": "pubmed",
            "year": "2024",
            "snippet": "Test abstract",
            "id": "TEST001",
        }
        with (
            patch("med_research.pipeline.evidence.extractor.API_KEY", "fake-key"),
            patch(
                "med_research.pipeline.evidence.extractor.call_llm",
                return_value="not valid json at all",
            ),
        ):
            result = extract_evidence(article, "test query", use_cache=False)
            assert result is not None
            assert "not valid json at all" in result.get("key_findings", "")

    def test_extract_with_partial_json(self):
        """Handles partial JSON (missing fields) gracefully."""
        article = {
            "title": "Test Article",
            "source": "Test Journal",
            "source_type": "pubmed",
            "year": "2024",
            "snippet": "Test abstract",
            "id": "TEST001",
        }
        with (
            patch("med_research.pipeline.evidence.extractor.API_KEY", "fake-key"),
            patch(
                "med_research.pipeline.evidence.extractor.call_llm",
                return_value='{"evidence_level": "rct", "model_system": "human"}',
            ),
        ):
            result = extract_evidence(article, "test query", use_cache=False)
            assert result is not None
            assert result["evidence_level"] == "rct"
            assert result["model_system"] == "human"
            # Missing fields get defaults
            assert result["key_findings"] == ""
            assert result["drugs_mentioned"] == []


# ── Extract All (No-API Mode) Tests ──────────────────────────────────────


class TestExtractAllNoAPI:
    @pytest.fixture(autouse=True)
    def _isolate_cache(self, tmp_path, monkeypatch):
        """Write to a temp cache instead of the tracked pipeline data dir."""
        monkeypatch.setattr("med_research.pipeline.evidence.extractor.DATA_DIR", tmp_path)
        monkeypatch.setattr(
            "med_research.pipeline.evidence.extractor.CACHE_PATH",
            tmp_path / "extraction_cache.json",
        )

    def test_extract_all_without_api_key(self, monkeypatch):
        """extract_all without API key returns error dict."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with patch("med_research.pipeline.evidence.extractor.API_KEY", ""):
            result = extract_all("lupus", sources=["pubmed"], max_articles=3, use_cache=True)
            assert result["total_extracted"] == 0
            assert result["status"] == "blocked"
            assert result["coverage"]["module"] == "evidence_extract"
            assert "error" in result


# ── Slow / Live Tests ────────────────────────────────────────────────────


@pytest.mark.slow
class TestExtractionLive:
    def test_extract_all_requires_api_key(self):
        """extract_all returns error when no API key is set."""
        import os

        if not os.environ.get("OPENAI_API_KEY"):
            result = extract_all(
                "lupus rituximab",
                sources=["pubmed"],
                max_articles=2,
                use_cache=True,
            )
            assert "error" in result

    def test_extraction_response_structure(self):
        """Verify extraction response has correct structure when API key set."""
        import os

        if os.environ.get("OPENAI_API_KEY"):
            result = extract_all(
                "lupus nephritis treatment",
                sources=["pubmed"],
                max_articles=1,
                use_cache=True,
            )
            assert "query" in result
            assert "model" in result
            assert "total_extracted" in result
            assert "extractions" in result
            assert "stats" in result
