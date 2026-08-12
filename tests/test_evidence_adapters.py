"""Contract tests for evidence pipeline module adapters."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

# Register evidence adapters for registry-backed tests.
import med_research.pipeline.evidence.adapter  # noqa: F401
from med_research.pipeline.evidence.adapter import (
    EvidenceGathererModule,
    EvidenceMonitorModule,
    LLMExtractorModule,
)
from med_research.pipeline.provenance import build_provenance
from med_research.pipeline.registry import MODULE_REGISTRY, get_module
from tests.test_pipeline_base import ModuleAdapterContract

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _openai_api_key(monkeypatch):
    """Evidence extract coverage requires an API key."""


    monkeypatch.setenv("OPENAI_API_KEY", "test-key-for-adapters")


class TestEvidenceGathererAdapter(ModuleAdapterContract):
    module_cls = EvidenceGathererModule
    module_id = "evidence_gather"
    coverage_module = "evidence_gather"
    coverage_inputs = ("genes", "drugs", "pathways", "pubmed_queries")

    def test_build_provenance_matches_engine_main(self):
        module = self.module_cls()
        provenance = module.build_provenance(self.disease_id)
        expected = build_provenance(
            disease_id=self.disease_id,
            module=module.module_id,
            sources=[
                "pubmed",
                "preprints",
                "clinical_trials",
                "fda_labels",
                "patents",
            ],
            query=module.build_provenance(self.disease_id)["query"],
            cache_or_live="cache",
        )

        for key in ("disease_id", "module", "sources", "cache_or_live", "query"):
            assert provenance[key] == expected[key]

    def test_run_matches_engine(self):
        module = self.module_cls()
        disease_id = self.disease_id
        query = module.build_provenance(disease_id)["query"]
        kwargs = {
            "query": query,
            "sources": ["pubmed"],
            "max_per_source": 3,
            "use_cache": True,
        }

        from med_research.pipeline.evidence.gatherer import gather_evidence

        direct = gather_evidence(
            query, disease_id=disease_id, **{k: v for k, v in kwargs.items() if k != "query"}
        )
        wrapped = module.run(disease_id, **kwargs)

        assert isinstance(wrapped, dict)
        assert wrapped.keys() == direct.keys()
        assert wrapped["total_results"] == direct["total_results"]
        assert wrapped["status"] == direct["status"]

    def test_report_returns_path(self):
        module = self.module_cls()
        disease_id = self.disease_id
        results = module.run(
            disease_id,
            sources=["pubmed"],
            max_per_source=3,
            use_cache=True,
        )
        assert results["status"] != "blocked"

        provenance = module.build_provenance(disease_id, run_id="evidence-adapter-test")
        report_path = module.report(results, disease_id, provenance=provenance)

        assert isinstance(report_path, Path)
        assert report_path.exists()
        html = report_path.read_text(encoding="utf-8")
        assert provenance["fingerprint"][:12] in html


class TestLLMExtractorAdapter(ModuleAdapterContract):
    module_cls = LLMExtractorModule
    module_id = "llm_extractor"
    coverage_module = "evidence_extract"
    coverage_inputs = ()

    def test_build_provenance_matches_engine_main(self):
        module = self.module_cls()
        provenance = module.build_provenance(self.disease_id)
        expected = build_provenance(
            disease_id=self.disease_id,
            module=module.module_id,
            sources=["pubmed", "preprints", "clinical_trials"],
            query=provenance["query"],
            cache_or_live="cache",
        )

        for key in ("disease_id", "module", "sources", "cache_or_live", "query"):
            assert provenance[key] == expected[key]

    def test_run_matches_engine(self):
        module = self.module_cls()
        disease_id = self.disease_id
        query = module.build_provenance(disease_id)["query"]
        kwargs = {
            "query": query,
            "sources": ["pubmed"],
            "max_articles": 2,
            "use_cache": True,
        }

        sample_evidence = {
            "all_results": [
                {
                    "id": "PMID-adapter-test",
                    "title": "RA treatment trial",
                    "source": "Test Journal",
                    "source_type": "pubmed",
                    "year": "2024",
                    "snippet": "Sample abstract for adapter contract test.",
                    "url": "https://example.com/article",
                }
            ],
            "total_results": 1,
        }
        sample_extraction = {
            "evidence_level": "rct",
            "model_system": "human",
            "key_findings": "Sample finding.",
            "drugs_mentioned": ["Methotrexate"],
            "disease": "Rheumatoid Arthritis",
            "study_design": "double_blind_rct",
            "sample_size": 100,
            "p_value": "0.01",
            "effect_size": None,
            "relevance_to_query": 80,
            "confidence": 75,
        }

        with (
            patch(
                "med_research.pipeline.evidence.extractor.API_KEY",
                "test-key-for-adapters",
            ),
            patch(
                "med_research.pipeline.evidence.extractor.gather_evidence",
                return_value=sample_evidence,
            ),
            patch(
                "med_research.pipeline.evidence.extractor.extract_evidence",
                return_value=sample_extraction,
            ),
        ):
            from med_research.pipeline.evidence.extractor import extract_all

            direct = extract_all(
                query, disease_id=disease_id, **{k: v for k, v in kwargs.items() if k != "query"}
            )
            wrapped = module.run(disease_id, **kwargs)

        assert isinstance(wrapped, dict)
        assert wrapped["total_extracted"] == direct["total_extracted"]
        assert wrapped["status"] == direct["status"]
        assert wrapped["extractions"][0]["evidence_level"] == "rct"

    def test_report_returns_path(self):
        module = self.module_cls()
        disease_id = self.disease_id
        results = {
            "query": "rheumatoid arthritis treatment",
            "model": "gpt-4o-mini",
            "total_extracted": 1,
            "successful_extractions": 1,
            "elapsed_seconds": 0.1,
            "extractions": [
                {
                    "title": "RA treatment trial",
                    "source_type": "pubmed",
                    "source": "Test Journal",
                    "year": "2024",
                    "url": "https://example.com/article",
                    "id": "PMID-adapter-test",
                    "evidence_level": "rct",
                    "model_system": "human",
                    "key_findings": "Sample finding.",
                    "drugs_mentioned": ["Methotrexate"],
                    "disease": "Rheumatoid Arthritis",
                    "study_design": "double_blind_rct",
                    "sample_size": 100,
                    "p_value": "0.01",
                    "effect_size": None,
                    "relevance_to_query": 80,
                    "confidence": 75,
                }
            ],
            "stats": {
                "evidence_levels": {"rct": 1},
                "model_systems": {"human": 1},
                "study_designs": {"double_blind_rct": 1},
                "unique_drugs_mentioned": ["Methotrexate"],
                "n_unique_drugs": 1,
                "avg_confidence": 75.0,
                "avg_relevance": 80.0,
            },
            "status": "ready",
        }

        provenance = module.build_provenance(disease_id, run_id="evidence-adapter-test")
        report_path = module.report(results, disease_id, provenance=provenance)

        assert isinstance(report_path, Path)
        assert report_path.exists()
        html = report_path.read_text(encoding="utf-8")
        assert provenance["fingerprint"][:12] in html


class TestEvidenceMonitorAdapter(ModuleAdapterContract):
    module_cls = EvidenceMonitorModule
    module_id = "evidence_monitor"
    coverage_module = "evidence_monitor"
    coverage_inputs = ("genes", "pubmed_queries")

    def test_build_provenance_matches_engine_main(self):
        module = self.module_cls()
        provenance = module.build_provenance(self.disease_id)
        expected = build_provenance(
            disease_id=self.disease_id,
            module=module.module_id,
            sources=["pubmed", "preprints", "clinical_trials"],
            cache_or_live="cache",
        )

        for key in ("disease_id", "module", "sources", "cache_or_live"):
            assert provenance[key] == expected[key]

    def test_run_matches_engine(self):
        module = self.module_cls()
        disease_id = self.disease_id
        sample_snapshot = {
            "snapshot_id": "20250101_120000",
            "timestamp": "2025-01-01T12:00:00",
            "tracked_queries": ["rheumatoid arthritis treatment"],
            "disease_id": disease_id,
            "tracked_drugs": [],
            "tracked_genes": [],
            "sources": ["pubmed"],
            "queries": {},
            "drugs": {},
            "genes": {},
            "status": "ready",
        }

        with patch(
            "med_research.pipeline.evidence.monitor.take_snapshot",
            return_value=sample_snapshot,
        ) as mock_take:
            from med_research.pipeline.evidence.monitor import take_snapshot

            direct = take_snapshot(
                sources=["pubmed"],
                max_per_query=2,
                disease_id=disease_id,
            )
            wrapped = module.run(
                disease_id,
                sources=["pubmed"],
                max_per_query=2,
            )

        mock_take.assert_called()
        assert wrapped["snapshot"] == direct
        assert wrapped["snapshot"]["snapshot_id"] == sample_snapshot["snapshot_id"]

    def test_report_returns_path(self):
        from med_research.pipeline.evidence.monitor import compare_snapshots

        module = self.module_cls()
        disease_id = self.disease_id
        prev = {
            "snapshot_id": "20250101_120000",
            "timestamp": "2025-01-01T12:00:00",
            "tracked_queries": ["rheumatoid arthritis treatment"],
            "tracked_drugs": [],
            "tracked_genes": [],
            "queries": {
                "rheumatoid arthritis treatment": {
                    "results": [
                        {
                            "id": "P1",
                            "title": "Paper One",
                            "source_type": "pubmed",
                            "year": "2024",
                            "url": "",
                        }
                    ],
                    "total": 1,
                    "hash": "abc",
                }
            },
            "drugs": {},
            "genes": {},
        }
        curr = {
            **prev,
            "snapshot_id": "20250102_120000",
            "timestamp": "2025-01-02T12:00:00",
            "queries": {
                "rheumatoid arthritis treatment": {
                    "results": [
                        {
                            "id": "P1",
                            "title": "Paper One",
                            "source_type": "pubmed",
                            "year": "2024",
                            "url": "",
                        },
                        {
                            "id": "P2",
                            "title": "Paper Two",
                            "source_type": "pubmed",
                            "year": "2025",
                            "url": "",
                        },
                    ],
                    "total": 2,
                    "hash": "def",
                }
            },
        }
        diff = compare_snapshots(prev, curr)
        results = {
            "diff": diff,
            "prev_snapshot": prev,
            "curr_snapshot": curr,
        }

        provenance = module.build_provenance(disease_id, run_id="evidence-adapter-test")
        report_path = module.report(results, disease_id, provenance=provenance)

        assert isinstance(report_path, Path)
        assert report_path.exists()
        html = report_path.read_text(encoding="utf-8")
        assert provenance["fingerprint"][:12] in html


def test_evidence_adapters_registered():
    for module_id in ("evidence_gather", "llm_extractor", "evidence_monitor"):
        assert module_id in MODULE_REGISTRY
        instance = get_module(module_id)
        assert instance.module_id == module_id
