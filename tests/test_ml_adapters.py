"""Contract tests for ML and semantic search pipeline adapters."""

from __future__ import annotations

import pytest

import med_research.pipeline.ml_predictor.adapter  # noqa: F401
import med_research.pipeline.semantic_search.adapter  # noqa: F401
from med_research.pipeline.ml_predictor.adapter import MlPredictorModule
from med_research.pipeline.provenance import build_provenance
from med_research.pipeline.semantic_search.adapter import (
    SemanticSearchModule,
    _default_query,
)
from med_research.pipeline.semantic_search.engine import SemanticSearchEngine
from tests.test_pipeline_base import ModuleAdapterContract

pytestmark = pytest.mark.unit


def _ml_deps_available() -> bool:
    try:
        import sklearn  # noqa: F401
        import xgboost  # noqa: F401
    except ImportError:
        return False
    return True


class TestMlPredictorAdapter(ModuleAdapterContract):
    module_cls = MlPredictorModule
    module_id = "ml_predictor"
    coverage_module = "ml_predictor"
    coverage_inputs = ("genes", "relationships")

    def test_build_provenance_matches_engine_main(self):
        module = self.module_cls()

        provenance = module.build_provenance(self.disease_id)
        expected = build_provenance(
            disease_id=self.disease_id,
            module=module.module_id,
            sources=["knowledge_graph"],
            cache_or_live="cache",
            scoring={"ranking": "druggability_score"},
        )

        for key in ("disease_id", "module", "sources", "cache_or_live", "scoring"):
            assert provenance[key] == expected[key]

    @pytest.mark.skipif(not _ml_deps_available(), reason="xgboost/scikit-learn not installed")
    def test_run_matches_engine(self):
        module = self.module_cls()
        disease_id = self.disease_id

        from med_research.pipeline.knowledge_graph.builder import build_graph
        from med_research.pipeline.ml_predictor.predictor import train_and_predict

        graph = build_graph(disease_id)
        direct = train_and_predict(graph, top_n=10)
        wrapped = module.run(disease_id, top=10)

        assert isinstance(wrapped, dict)
        assert "error" not in wrapped
        assert (
            wrapped["predictions"][0]["druggability_score"]
            == direct["predictions"][0]["druggability_score"]
        )
        assert len(wrapped["top_untargeted"]) == len(direct["top_untargeted"])

    @pytest.mark.skipif(not _ml_deps_available(), reason="xgboost/scikit-learn not installed")
    def test_report_returns_path(self):
        from pathlib import Path

        module = self.module_cls()
        disease_id = self.disease_id
        results = module.run(disease_id, top=10)
        assert "error" not in results

        provenance = module.build_provenance(disease_id, run_id="ml-adapter-test")
        report_path = module.report(results, disease_id, provenance=provenance)

        assert isinstance(report_path, Path)
        assert report_path.exists()
        html = report_path.read_text(encoding="utf-8")
        assert provenance["fingerprint"][:12] in html


class TestSemanticSearchAdapter(ModuleAdapterContract):
    module_cls = SemanticSearchModule
    module_id = "semantic_search"
    coverage_module = "semantic"
    coverage_inputs = ("genes", "drugs", "pubmed_queries")

    def test_build_provenance_matches_engine_main(self):
        module = self.module_cls()
        query = _default_query(self.disease_id)

        provenance = module.build_provenance(self.disease_id)
        expected = build_provenance(
            disease_id=self.disease_id,
            module=module.module_id,
            sources=["pubmed"],
            query=query,
            cache_or_live="cache",
        )

        for key in ("disease_id", "module", "sources", "query", "cache_or_live"):
            assert provenance[key] == expected[key]

    def test_run_matches_engine(self):
        module = self.module_cls()
        disease_id = self.disease_id
        query = _default_query(disease_id)

        engine = SemanticSearchEngine(disease_id=disease_id)
        direct = engine.search(query, top_k=5)
        wrapped = module.run(disease_id, query=query, top=5)

        assert isinstance(wrapped, dict)
        assert wrapped["query"] == query
        assert wrapped["results"] == direct
        assert wrapped["indexed_count"] == engine.get_indexed_count()

    def test_report_returns_path(self):
        from pathlib import Path

        module = self.module_cls()
        disease_id = self.disease_id
        payload = module.run(disease_id, top=5)

        provenance = module.build_provenance(
            disease_id,
            query=payload["query"],
            run_id="semantic-adapter-test",
        )
        report_path = module.report(payload, disease_id, provenance=provenance)

        assert isinstance(report_path, Path)
        assert report_path.exists()
        html = report_path.read_text(encoding="utf-8")
        assert provenance["fingerprint"][:12] in html
        assert payload["query"] in html
