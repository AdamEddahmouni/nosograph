"""Fixture-backed tests for web service registry wiring (no Redis required)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from med_research.pipeline.registry import get_module, list_modules
from med_research.web.main import app
from med_research.web.services.bioinformatics_service import run_gwas
from med_research.web.services.registry_service import (
    JOB_MODULE_IDS,
    ProgressReporter,
    execute_module,
    make_progress_reporter,
    report_module,
    resolve_module_id,
    run_module,
    run_module_job,
    standard_to_legacy,
)
from med_research.web.services.repurpose_service import get_gene_repurposing, run_repurposing
from med_research.web.services.synergy_service import run_synergy

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def client():
    """Shared FastAPI test client for router integration checks."""
    with TestClient(app) as test_client:
        yield test_client


class TestRegistryService:
    """Unit tests for the registry bridge helpers."""

    def test_list_modules_includes_core_adapters(self):
        modules = list_modules()
        assert "drug_repurposing" in modules
        assert "gwas" in modules
        assert "literature_mining" in modules
        assert "evidence_workspace" in modules
        assert len(modules) >= 20

    def test_job_module_ids_cover_celery_tasks(self):
        assert JOB_MODULE_IDS["gwas"] == "gwas"
        assert JOB_MODULE_IDS["synergy"] == "drug_synergy"
        assert JOB_MODULE_IDS["safety"] == "adverse_events"
        assert JOB_MODULE_IDS["literature"] == "literature_mining"
        assert JOB_MODULE_IDS["cart"] == "car_t_predictor"
        assert JOB_MODULE_IDS["workspace"] == "evidence_workspace"
        assert JOB_MODULE_IDS["knowledge_graph"] == "knowledge_graph"

    def test_resolve_module_id_accepts_aliases_and_module_ids(self):
        assert resolve_module_id("ml") == "ml_predictor"
        assert resolve_module_id("ml_predictor") == "ml_predictor"
        assert resolve_module_id("cart") == "car_t_predictor"

    def test_resolve_module_id_unknown_raises(self):
        with pytest.raises(KeyError, match="Unknown job module"):
            resolve_module_id("not_a_real_module")

    def test_standard_progress_converts_to_legacy_percent(self):
        calls: list[tuple[int, str]] = []

        def sink(percent: int, message: str) -> None:
            calls.append((percent, message))

        standard_to_legacy("fetching studies", 1, 4, sink)
        assert calls == [(25, "fetching studies")]

        standard_to_legacy("done", 4, 4, sink)
        assert calls[-1] == (100, "done")

    def test_progress_reporter_forwards_to_legacy_sink(self):
        sink = MagicMock()
        reporter = ProgressReporter(sink)
        reporter("enrichment", 2, 5)
        sink.assert_called_once_with(40, "enrichment")

    def test_make_progress_reporter_returns_callable(self):
        sink = MagicMock()
        reporter = make_progress_reporter(sink)
        reporter("complete", 1, 1)
        sink.assert_called_once_with(100, "complete")

    def test_run_module_delegates_to_registry(self):
        mock_module = MagicMock()
        mock_module.run.return_value = {"status": "ready", "data": [1, 2, 3]}

        with patch(
            "med_research.web.services.registry_service.get_module",
            return_value=mock_module,
        ):
            result = run_module("gwas", "ra", max_studies=10)

        mock_module.run.assert_called_once_with("ra", max_studies=10)
        assert result["status"] == "ready"

    def test_execute_module_delegates_to_dispatch(self):
        from med_research.pipeline.base import PipelineRunResult

        expected = PipelineRunResult(success=True, data={"ok": True})
        with patch(
            "med_research.web.services.registry_service._execute_module",
            return_value=expected,
        ) as mock_dispatch:
            result = execute_module("gwas", "ra")

        mock_dispatch.assert_called_once_with("gwas", "ra", export_html=False, progress_callback=None)
        assert result.success is True

    def test_report_module_builds_provenance_and_calls_report(self, tmp_path):
        mock_module = MagicMock()
        mock_module.build_provenance.return_value = {"module": "gwas"}
        mock_module.report.return_value = tmp_path / "report.html"

        with patch(
            "med_research.web.services.registry_service.get_module",
            return_value=mock_module,
        ):
            path = report_module("gwas", {"gwas_results": {}}, "ra")

        mock_module.build_provenance.assert_called_once_with("ra")
        mock_module.report.assert_called_once()
        assert path == tmp_path / "report.html"

    def test_run_module_job_dispatches_ml_with_disease_id(self):
        with patch(
            "med_research.web.services.shared_services.run_ml_prediction",
            return_value={"predictions": []},
        ) as mock_ml:
            result = run_module_job("ml", "ra", top_n=5)

        mock_ml.assert_called_once()
        assert mock_ml.call_args.kwargs["disease_id"] == "ra"
        assert result == {"predictions": []}


class TestWebServiceRegistryWiring:
    """Verify web services dispatch through registry adapters."""

    def test_repurpose_service_uses_registry(self):
        adapter = get_module("drug_repurposing")
        expected = adapter.run("ra")

        with patch(
            "med_research.web.services.repurpose_service.run_module",
            return_value=expected,
        ) as mock_run:
            result = run_repurposing(top_n=5, disease_id="ra")

        mock_run.assert_called_once_with("drug_repurposing", "ra")
        assert "candidates" in result
        assert "coverage" in result
        assert "status" in result

    def test_gene_repurposing_uses_registry(self):
        with patch(
            "med_research.web.services.repurpose_service.get_kg_genes",
            return_value={"STAT4": {"name": "STAT4", "category": "signaling"}},
        ), patch(
            "med_research.web.services.repurpose_service.run_module",
            return_value=[{"gene_id": "STAT4", "composite_score": 8.5}],
        ) as mock_run:
            result = get_gene_repurposing("STAT4", disease_id="ra")

        mock_run.assert_called_once_with(
            "drug_repurposing",
            "ra",
            gene_id="STAT4",
            untargeted_only=False,
        )
        assert result is not None
        assert result["gene_id"] == "STAT4"

    def test_synergy_service_uses_registry_with_progress(self):
        adapter = get_module("drug_synergy")
        expected = adapter.run("ra", save=True)

        progress = MagicMock()
        with patch(
            "med_research.web.services.synergy_service.run_module",
            return_value=expected,
        ) as mock_run:
            result = run_synergy(top_n=5, disease_id="ra", progress_callback=progress)

        mock_run.assert_called_once_with(
            "drug_synergy",
            "ra",
            progress_callback=progress,
            save=True,
        )
        assert "pairs" in result
        assert "total_pairs" in result

    def test_gwas_service_uses_registry(self):
        raw = {
            "status": "ready",
            "top_hits": [],
            "gwas_results": {"gene_associations": {}, "total_studies_analyzed": 0},
            "crossref": {},
        }

        with patch(
            "med_research.web.services.bioinformatics_service.run_module",
            return_value=raw,
        ) as mock_run:
            result = run_gwas(disease_id="ra", no_cache=False)

        mock_run.assert_called_once()
        assert mock_run.call_args.args[0] == "gwas"
        assert "top_hits" in result or result.get("status") == "blocked"

    def test_evidence_gather_service_uses_registry(self):
        from med_research.web.services.evidence_service import run_evidence_gather

        with patch(
            "med_research.web.services.evidence_service.run_module",
            return_value={"results": [], "all_results": [], "status": "ready"},
        ) as mock_run:
            result = run_evidence_gather(
                query="lupus treatment",
                disease_id="sle",
                use_cache=True,
            )

        mock_run.assert_called_once_with(
            "evidence_gather",
            "sle",
            query="lupus treatment",
            sources=None,
            max_per_source=20,
            use_cache=True,
        )
        assert "results" in result

    def test_llm_extractor_service_uses_registry(self):
        from med_research.web.services.extractor_service import run_llm_extraction

        with patch(
            "med_research.web.services.extractor_service.run_module",
            return_value={"extractions": []},
        ) as mock_run:
            run_llm_extraction(query="test", disease_id="ra")

        mock_run.assert_called_once_with(
            "llm_extractor",
            "ra",
            query="test",
            sources=None,
            max_articles=20,
            model=None,
            use_cache=True,
        )

    def test_car_t_service_uses_registry(self):
        from med_research.web.services.car_t_service import run_cart_analysis

        adapter = get_module("car_t_predictor")
        expected = adapter.run("ra")

        with patch(
            "med_research.web.services.car_t_service.run_module",
            return_value=expected,
        ) as mock_run:
            result = run_cart_analysis(disease_id="ra")

        mock_run.assert_called_once_with("car_t_predictor", "ra")
        assert "genes" in result
        assert "coverage" in result

    def test_semantic_service_uses_registry(self):
        from med_research.web.services.semantic_service import run_semantic_search

        with patch(
            "med_research.web.services.semantic_service.run_module",
            return_value={"results": [], "query": "test", "indexed_count": 0},
        ) as mock_run:
            result = run_semantic_search("test query", disease_id="ra")

        mock_run.assert_called_once_with("semantic_search", "ra", query="test query", top=20)
        assert result["query"] == "test query"
        assert "results" in result

    def test_kg_service_uses_execute_module(self):
        from med_research.pipeline.base import PipelineRunResult
        from med_research.web.services.kg_service import get_graph_stats

        mock_graph = MagicMock()
        mock_graph.nodes.return_value = []
        mock_graph.edges.return_value = []
        mock_graph.number_of_nodes.return_value = 0
        mock_graph.number_of_edges.return_value = 0

        with patch(
            "med_research.web.services.kg_service.execute_module",
            return_value=PipelineRunResult(success=True, data=mock_graph),
        ):
            result = get_graph_stats(disease_id="ra")

        assert "coverage" in result
        assert "status" in result

    def test_cross_disease_comparative_uses_registry(self):
        from med_research.web.services.cross_disease_service import run_comparative_modules

        with patch(
            "med_research.web.services.cross_disease_service.run_module",
            return_value={"diseases": [], "modules": {}},
        ) as mock_run:
            result = run_comparative_modules(top_synergy=3)

        mock_run.assert_called_once_with(
            "cross_disease",
            "sle",
            comparative=True,
            top_synergy=3,
        )
        assert "diseases" in result


class TestGenericJobRouter:
    """Tests for POST /api/jobs/{module_id} and GET /api/system/modules."""

    def test_submit_generic_module_job(self, client):
        with patch("med_research.web.routers.jobs.task_run_module") as mock_task:
            mock_task.delay.return_value.id = "00000000-0000-0000-0000-000000000001"
            resp = client.post("/api/jobs/ml_predictor", params={"top_n": 5, "disease_id": "ra"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["job_id"] == "00000000-0000-0000-0000-000000000001"
        assert data["module"] == "ml_predictor"
        mock_task.delay.assert_called_once_with("ml_predictor", "ra", top_n=5)

    def test_submit_unknown_module_job_404(self, client):
        resp = client.post("/api/jobs/not_a_module")
        assert resp.status_code == 404

    def test_submit_generic_job_unknown_disease_422(self, client):
        resp = client.post(
            "/api/jobs/ml_predictor",
            params={"disease_id": "not_a_disease", "top_n": 5},
        )
        assert resp.status_code == 422

    def test_submit_generic_job_unknown_option_422(self, client):
        resp = client.post(
            "/api/jobs/ml_predictor",
            params={"top_n": 5, "bogus_option": "yes"},
        )
        assert resp.status_code == 422

    def test_submit_generic_job_invalid_top_n_422(self, client):
        resp = client.post(
            "/api/jobs/ml_predictor",
            params={"top_n": 0},
        )
        assert resp.status_code == 422

    def test_list_system_modules(self, client):
        resp = client.get("/api/system/modules", params={"disease": "ra"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["disease_id"] == "ra"
        assert data["count"] >= 20
        module_ids = {m["module_id"] for m in data["modules"]}
        assert "knowledge_graph" in module_ids
        assert "evidence_workspace" in module_ids
        first = data["modules"][0]
        assert "depends_on" in first
        assert "coverage" in first

