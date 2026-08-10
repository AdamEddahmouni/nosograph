"""Fixture-backed tests for web service registry wiring (no Redis required)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from med_research.exceptions import ModuleNotAvailableError
from med_research.pipeline.base import PipelineRunResult
from med_research.pipeline.registry import get_module, list_modules
from med_research.web.main import app
from med_research.web.services.bioinformatics_service import run_gwas
from med_research.web.services.registry_service import (
    JOB_MODULE_IDS,
    MODULE_OPTS_MAPPERS,
    ProgressReporter,
    dispatch_sync_module,
    execute_module,
    make_progress_reporter,
    report_module,
    resolve_module_id,
    run_all_pipeline,
    run_module_job,
    standard_to_legacy,
)
from med_research.web.services.repurpose_service import get_gene_repurposing, run_repurposing
from med_research.web.services.synergy_service import run_synergy

# One representative Celery route alias per registered module target.
_MODULE_ROUTE_CASES = sorted(
    {resolved: route for route, resolved in JOB_MODULE_IDS.items()}.items(),
    key=lambda item: item[0],
)


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

    def test_job_module_ids_are_generated_from_registry_catalog(self):
        from med_research.pipeline.registry import module_job_aliases

        assert module_job_aliases() == JOB_MODULE_IDS
        assert JOB_MODULE_IDS["drug_repurposing"] == "drug_repurposing"
        assert JOB_MODULE_IDS["repurpose"] == "drug_repurposing"

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

    def test_execute_module_delegates_to_dispatch(self):
        from med_research.pipeline.base import PipelineRunResult

        expected = PipelineRunResult(success=True, data={"ok": True})
        with patch(
            "med_research.web.services.registry_service.pipeline_gateway.execute",
            return_value=expected,
        ) as mock_dispatch:
            result = execute_module("gwas", "ra")

        mock_dispatch.assert_called_once_with("gwas", "ra", export_html=False, progress_callback=None)
        assert result.success is True

    def test_report_module_delegates_to_centralized_dispatch(self, tmp_path) -> None:
        expected_path = tmp_path / "report.html"
        with patch(
            "med_research.web.services.registry_service.pipeline_gateway.report",
            return_value=expected_path,
        ) as mock_report:
            path = report_module("gwas", {"gwas_results": {}}, "ra", run_id="test")

        mock_report.assert_called_once_with(
            "gwas",
            {"gwas_results": {}},
            "ra",
            run_id="test",
        )
        assert path == expected_path

    def test_dispatch_sync_module_raises_on_blocked(self):
        expected = PipelineRunResult(success=False, data=None, errors=["blocked module"])
        with patch(
            "med_research.web.services.registry_service.execute_module",
            return_value=expected,
        ), pytest.raises(ModuleNotAvailableError, match="blocked module"):
            dispatch_sync_module("gwas", "ra")

    def test_run_module_job_includes_report_path_when_export_html(self):
        from pathlib import Path

        report = Path("/tmp/report.html")
        expected = PipelineRunResult(
            success=True,
            data={"predictions": []},
            report_path=report,
        )
        with patch(
            "med_research.web.services.registry_service.execute_module",
            return_value=expected,
        ) as mock_dispatch:
            result = run_module_job("ml", "ra", top_n=5, export_html=True)

        assert mock_dispatch.call_args.kwargs["export_html"] is True
        assert result["report_path"] == str(report)
        assert result["predictions"] == []

    def test_run_module_job_dispatches_ml_through_execute_module(self):
        expected = PipelineRunResult(success=True, data={"predictions": []})
        with patch(
            "med_research.web.services.registry_service.execute_module",
            return_value=expected,
        ) as mock_dispatch:
            result = run_module_job("ml", "ra", top_n=5)

        mock_dispatch.assert_called_once()
        call_args, call_kwargs = mock_dispatch.call_args
        assert call_args == ("ml_predictor", "ra")
        assert call_kwargs["export_html"] is False
        assert call_kwargs["top"] == 5
        assert result == {"predictions": []}

    @pytest.mark.parametrize("resolved_id,route_id", _MODULE_ROUTE_CASES)
    def test_run_module_job_dispatches_every_registered_module(
        self, resolved_id: str, route_id: str
    ):
        """Every JOB_MODULE_IDS target routes through execute_module."""
        mock_graph = MagicMock()
        mock_graph.number_of_nodes.return_value = 3
        mock_graph.number_of_edges.return_value = 7
        payload = mock_graph if resolved_id == "knowledge_graph" else {"status": "ready"}
        expected = PipelineRunResult(success=True, data=payload)

        with patch(
            "med_research.web.services.registry_service.execute_module",
            return_value=expected,
        ) as mock_dispatch:
            result = run_module_job(route_id, "ra")

        mock_dispatch.assert_called_once()
        call_args, call_kwargs = mock_dispatch.call_args
        assert call_args[0] == resolved_id
        assert call_args[1] == "ra"
        assert call_kwargs["export_html"] is False
        assert resolved_id in MODULE_OPTS_MAPPERS

        if resolved_id == "knowledge_graph":
            assert result == {"nodes": 3, "edges": 7, "status": "ready"}
        else:
            assert result == payload

    def test_run_module_job_raises_on_dispatch_failure(self):
        from med_research.exceptions import PipelineExecutionError

        expected = PipelineRunResult(success=False, data=None, errors=["blocked"])
        with patch(
            "med_research.web.services.registry_service.execute_module",
            return_value=expected,
        ), pytest.raises(PipelineExecutionError, match="blocked"):
            run_module_job("gwas", "ra")

    def test_require_runnable_coverage_raises_with_limitation(self):
        from med_research.diseases.coverage import ModuleCoverage
        from med_research.exceptions import ModuleNotAvailableError
        from med_research.web.services.registry_service import require_runnable_coverage

        coverage = ModuleCoverage(
            disease_id="ra",
            module="gwas",
            level="none",
            status="blocked",
            limitations=["GWAS data missing"],
        )
        with pytest.raises(ModuleNotAvailableError, match="GWAS data missing"):
            require_runnable_coverage(coverage, "gwas")

    def test_require_runnable_coverage_raises_with_missing_inputs(self):
        from med_research.diseases.coverage import ModuleCoverage
        from med_research.exceptions import ModuleNotAvailableError
        from med_research.web.services.registry_service import require_runnable_coverage

        coverage = ModuleCoverage(
            disease_id="ra",
            module="ml_predictor",
            level="none",
            status="blocked",
            missing_inputs=["genes", "relationships"],
        )
        with pytest.raises(ModuleNotAvailableError, match="genes"):
            require_runnable_coverage(coverage)

    def test_require_module_data_success_and_failure(self):
        from med_research.exceptions import ModuleNotAvailableError
        from med_research.web.services.registry_service import require_module_data

        ok = PipelineRunResult(success=True, data={"value": 1})
        assert require_module_data(ok, "gwas") == {"value": 1}

        blocked = PipelineRunResult(success=False, data=None, errors=["blocked module"])
        with pytest.raises(ModuleNotAvailableError, match="blocked module"):
            require_module_data(blocked, "gwas")

    def test_dispatch_sync_module_delegates_to_execute_module(self):
        from med_research.web.services.registry_service import dispatch_sync_module

        expected = PipelineRunResult(success=True, data={"hits": []})
        with patch(
            "med_research.web.services.registry_service.execute_module",
            return_value=expected,
        ) as mock_exec:
            data = dispatch_sync_module("gwas", "ra", max_studies=5)
        mock_exec.assert_called_once_with(
            "gwas", "ra", export_html=False, progress_callback=None, max_studies=5
        )
        assert data == {"hits": []}

    def test_run_all_pipeline_sequential_no_cache_runs_bioinformatics(self):

        calls: list[str] = []

        def fake_execute(module_id, disease_id, **kwargs):
            calls.append(module_id)
            data = MagicMock() if module_id == "knowledge_graph" else {}
            return PipelineRunResult(success=True, data=data)

        with patch(
            "med_research.web.services.registry_service.execute_module",
            side_effect=fake_execute,
        ), patch("med_research.pipeline.knowledge_graph.builder.export_for_web"):
            result = run_all_pipeline("ra", no_cache=True, parallel=False)

        for bio_id in ("gwas", "enrichment", "ppi"):
            assert bio_id in calls
        assert result["status"] == "success"
        assert result["disease_id"] == "ra"

    def test_run_module_job_single_drug_safety_shortcut(self):
        with patch(
            "med_research.web.services.registry_service._single_drug_safety_result",
            return_value={"drug_id": "belimumab"},
        ) as mock_safety:
            result = run_module_job("safety", "ra", drug_id="belimumab")
        mock_safety.assert_called_once_with("belimumab", "ra")
        assert result["drug_id"] == "belimumab"

    def test_run_all_pipeline_parallel_mode(self):

        calls: list[str] = []

        def fake_execute(module_id, disease_id, **kwargs):
            calls.append(module_id)
            data = MagicMock() if module_id == "knowledge_graph" else {}
            return PipelineRunResult(success=True, data=data)

        def fake_validate(module_ids):
            return [["knowledge_graph"], module_ids[1:]]

        def fake_run_levels(levels, runner, *, parallel, max_workers=None):
            for level in levels:
                for module_id in level:
                    runner(module_id)

        with patch(
            "med_research.web.services.registry_service.execute_module",
            side_effect=fake_execute,
        ), patch(
            "med_research.pipeline.scheduler.validate_dag",
            fake_validate,
        ), patch(
            "med_research.pipeline.scheduler.run_levels",
            fake_run_levels,
        ), patch("med_research.pipeline.knowledge_graph.builder.export_for_web"):
            result = run_all_pipeline("ra", parallel=True, full=False)

        assert "knowledge_graph" in calls
        assert result["status"] == "success"


class TestWebServiceRegistryWiring:
    """Verify web services dispatch through registry adapters."""

    def test_repurpose_service_uses_registry(self):
        adapter = get_module("drug_repurposing")
        expected = adapter.run("ra")

        with patch(
            "med_research.web.services.repurpose_service.dispatch_sync_module",
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
            "med_research.web.services.repurpose_service.dispatch_sync_module",
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
            "med_research.web.services.synergy_service.dispatch_sync_module",
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
            "med_research.web.services.bioinformatics_service.dispatch_sync_module",
            return_value=raw,
        ) as mock_run:
            result = run_gwas(disease_id="ra", no_cache=False)

        mock_run.assert_called_once()
        assert mock_run.call_args.args[0] == "gwas"
        assert "top_hits" in result

    def test_evidence_gather_service_uses_registry(self):
        from med_research.web.services.evidence_service import run_evidence_gather

        with patch(
            "med_research.web.services.evidence_service.dispatch_sync_module",
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
            "med_research.web.services.extractor_service.dispatch_sync_module",
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
            "med_research.web.services.car_t_service.dispatch_sync_module",
            return_value=expected,
        ) as mock_run:
            result = run_cart_analysis(disease_id="ra")

        mock_run.assert_called_once_with("car_t_predictor", "ra")
        assert "genes" in result
        assert "coverage" in result

    def test_semantic_service_uses_registry(self):
        from med_research.web.services.semantic_service import run_semantic_search

        with patch(
            "med_research.web.services.semantic_service.dispatch_sync_module",
            return_value={"results": [], "query": "test", "indexed_count": 0},
        ) as mock_run:
            result = run_semantic_search("test query", disease_id="ra")

        mock_run.assert_called_once_with("semantic_search", "ra", query="test query", top=20)
        assert result["query"] == "test query"
        assert "results" in result

    def test_kg_service_uses_dispatch_sync_module(self):
        from med_research.web.services.kg_service import get_graph_stats

        mock_graph = MagicMock()
        mock_graph.nodes.return_value = []
        mock_graph.edges.return_value = []
        mock_graph.number_of_nodes.return_value = 0
        mock_graph.number_of_edges.return_value = 0

        with patch(
            "med_research.web.services.kg_service.dispatch_sync_module",
            return_value=mock_graph,
        ):
            result = get_graph_stats(disease_id="ra")

        assert "coverage" in result
        assert "status" in result

    def test_cross_disease_comparative_uses_registry(self):
        from med_research.web.services.cross_disease_service import run_comparative_modules

        with patch(
            "med_research.web.services.cross_disease_service.dispatch_sync_module",
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

    def test_submit_run_all_job(self, client):
        with patch("med_research.web.routers.jobs.task_run_all") as mock_task:
            mock_task.delay.return_value.id = "00000000-0000-0000-0000-000000000003"
            resp = client.post(
                "/api/jobs/run-all",
                params={"disease_id": "sle", "skip_ml": True},
            )

        assert resp.status_code == 200
        assert resp.json()["module"] == "run-all"
        mock_task.delay.assert_called_once_with("sle", skip_ml=True)

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

    def test_submit_generic_job_rejects_option_outside_module_schema(self, client):
        resp = client.post("/api/jobs/cross_disease", params={"top_n": 5})
        assert resp.status_code == 422
        assert "Unknown request options" in resp.json()["detail"]

    def test_submit_generic_job_invalid_top_n_422(self, client):
        resp = client.post(
            "/api/jobs/ml_predictor",
            params={"top_n": 0},
        )
        assert resp.status_code == 422

    def test_generated_module_job_openapi_uses_catalog_schema(self):
        operation = app.openapi()["paths"]["/api/jobs/cross_disease"]["post"]
        parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}
        assert {"disease_id", "comparative", "top_synergy"}.issubset(parameters)
        top_schema = parameters["top_synergy"]["schema"]
        assert any(option.get("minimum") == 1 for option in top_schema["anyOf"])
        assert parameters["comparative"]["schema"]["anyOf"][0]["type"] == "boolean"

    @pytest.mark.parametrize(
        ("route", "module_id"),
        [
            ("gwas", "gwas"),
            ("enrichment", "enrichment"),
            ("ppi", "ppi"),
            ("literature", "literature_mining"),
            ("screening", "virtual_screening"),
            ("trials", "clinical_trials"),
            ("ml", "ml_predictor"),
            ("synergy", "drug_synergy"),
            ("safety", "adverse_events"),
        ],
    )
    def test_specialized_job_openapi_uses_catalog_schema(self, route, module_id):
        """Legacy job paths document the same options as their registry module."""
        from med_research.pipeline.registry import module_request_schema

        operation = app.openapi()["paths"][f"/api/jobs/{route}"]["post"]
        parameter_names = {
            parameter["name"]
            for parameter in operation.get("parameters", [])
            if parameter["name"] != "request"
        }
        assert parameter_names == {
            "disease_id",
            *module_request_schema(module_id)["properties"],
        }

    def test_specialized_job_openapi_preserves_registry_constraints(self):
        operation = app.openapi()["paths"]["/api/jobs/gwas"]["post"]
        parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}
        assert parameters["max_studies"]["schema"]["anyOf"][0]["minimum"] == 1

        from med_research.web.models.jobs import module_job_request_model

        generated_schema = module_job_request_model("gwas").model_json_schema()["properties"]
        assert generated_schema["max_studies"]["default"] == 30
        assert generated_schema["use_cache"]["default"] is True

    def test_specialized_job_options_forward_to_legacy_tasks(self, client):
        with patch("med_research.web.routers.jobs.task_run_gwas") as mock_gwas:
            mock_gwas.delay.return_value.id = "00000000-0000-0000-0000-000000000019"
            response = client.post(
                "/api/jobs/gwas",
                params={"use_cache": False, "resolve_snps": False},
            )
        assert response.status_code == 200
        mock_gwas.delay.assert_called_once_with(
            max_studies=30,
            no_cache=False,
            disease_id="sle",
            use_cache=False,
            resolve_snps=False,
        )

        with patch("med_research.web.routers.jobs.task_run_ppi") as mock_ppi:
            mock_ppi.delay.return_value.id = "00000000-0000-0000-0000-000000000020"
            response = client.post(
                "/api/jobs/ppi",
                params={"expand_neighbors": 2},
            )
        assert response.status_code == 200
        mock_ppi.delay.assert_called_once_with(
            confidence=0.4,
            no_cache=False,
            disease_id="sle",
            expand_neighbors=2,
        )

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
        assert "aliases" in first
        assert "coverage_inputs" in first
        assert "coverage_module" in first
        assert "result_contract" in first
        assert "response_schema" in first
        assert "request_schema" in first
        assert "coverage" in first
        workspace = next(
            module for module in data["modules"] if module["module_id"] == "evidence_workspace"
        )
        assert workspace["persisted_request_schema_version"] == "1.0"
        assert workspace["persisted_result_schema_version"] == "1.1"
        assert workspace["persisted_request_schema"]["properties"]["schema_version"]["const"] == "1.0"
        assert workspace["persisted_result_schema"]["properties"]["schema_version"]["const"] == "1.1"

    def test_list_system_modules_uses_pipeline_gateway_for_coverage(self, client):
        from med_research.diseases.coverage import ModuleCoverage

        coverage = ModuleCoverage(
            disease_id="ra",
            module="test",
            level="full",
            status="ready",
        )
        with patch(
            "med_research.web.routers.system.pipeline_gateway.coverage",
            return_value=coverage,
        ) as mock_coverage:
            resp = client.get("/api/system/modules", params={"disease": "ra"})

        assert resp.status_code == 200
        data = resp.json()
        assert mock_coverage.call_count == data["count"]
        mock_coverage.assert_any_call("gwas", "ra")
        assert all(module["coverage"]["status"] == "ready" for module in data["modules"])


class TestPipelineErrors:
    """Unit tests for pipeline_errors exit-code mapping."""

    def test_pipeline_exit_code_module_not_available(self):
        from med_research.exceptions import ModuleNotAvailableError
        from med_research.pipeline_errors import EXIT_COVERAGE_BLOCKED, pipeline_exit_code

        assert pipeline_exit_code(ModuleNotAvailableError("blocked")) == EXIT_COVERAGE_BLOCKED

    def test_pipeline_exit_code_configuration(self):
        from med_research.exceptions import ConfigurationError
        from med_research.pipeline_errors import EXIT_CONFIG, pipeline_exit_code

        assert pipeline_exit_code(ConfigurationError("bad config")) == EXIT_CONFIG

    def test_pipeline_exit_code_pipeline_execution(self):
        from med_research.exceptions import PipelineExecutionError
        from med_research.pipeline_errors import EXIT_RUNTIME, pipeline_exit_code

        assert pipeline_exit_code(PipelineExecutionError("failed")) == EXIT_RUNTIME

    def test_pipeline_exit_code_med_research(self):
        from med_research.exceptions import MedResearchError
        from med_research.pipeline_errors import EXIT_RUNTIME, pipeline_exit_code

        assert pipeline_exit_code(MedResearchError("generic")) == EXIT_RUNTIME

    def test_pipeline_exit_code_unknown_exception(self):
        from med_research.pipeline_errors import EXIT_RUNTIME, pipeline_exit_code

        assert pipeline_exit_code(ValueError("unexpected")) == EXIT_RUNTIME

    def test_handle_pipeline_error_module_not_available(self):
        from med_research.exceptions import ModuleNotAvailableError
        from med_research.pipeline_errors import EXIT_COVERAGE_BLOCKED, handle_pipeline_error

        code = handle_pipeline_error(ModuleNotAvailableError("no GWAS"), context="gwas")
        assert code == EXIT_COVERAGE_BLOCKED

    def test_handle_pipeline_error_configuration(self):
        from med_research.exceptions import ConfigurationError
        from med_research.pipeline_errors import EXIT_CONFIG, handle_pipeline_error

        code = handle_pipeline_error(ConfigurationError("missing API key"), context="literature")
        assert code == EXIT_CONFIG

    def test_handle_pipeline_error_pipeline_execution(self):
        from med_research.exceptions import PipelineExecutionError
        from med_research.pipeline_errors import EXIT_RUNTIME, handle_pipeline_error

        code = handle_pipeline_error(PipelineExecutionError("timeout"), context="ppi")
        assert code == EXIT_RUNTIME

    def test_handle_pipeline_error_med_research(self):
        from med_research.exceptions import MedResearchError
        from med_research.pipeline_errors import EXIT_RUNTIME, handle_pipeline_error

        code = handle_pipeline_error(MedResearchError("data error"))
        assert code == EXIT_RUNTIME

    def test_handle_pipeline_error_unknown_exception(self):
        from med_research.pipeline_errors import EXIT_RUNTIME, handle_pipeline_error

        code = handle_pipeline_error(RuntimeError("boom"), context="ml")
        assert code == EXIT_RUNTIME


class TestTypesModule:
    """Smoke tests for TypedDict shapes in types.py."""

    def test_pathway_dict_optional_fields(self):
        from med_research.types import PathwayDict

        pathway: PathwayDict = {"id": "type1-ifn", "name": "Type I IFN"}
        assert pathway["id"] == "type1-ifn"

    def test_candidate_dict_scoring_fields(self):
        from med_research.types import CandidateDict

        candidate: CandidateDict = {
            "gene_id": "BTK",
            "drug_name": "ibrutinib",
            "composite_score": 7.5,
            "tier": "tier1",
        }
        assert candidate["composite_score"] == 7.5

    def test_pipeline_result_envelope(self):
        from med_research.types import PipelineResult

        result: PipelineResult = {"success": True, "data": {"nodes": 10}, "errors": []}
        assert result["success"] is True

    def test_kg_entity_index_shape(self):
        from med_research.types import KGEntityIndex

        index: KGEntityIndex = {
            "genes": {"BTK": {"id": "BTK", "name": "BTK"}},
            "drugs": {},
            "pathways": {},
        }
        assert "BTK" in index["genes"]


class TestRunAllNoCacheBioinformatics:
    """run-all --no-cache must still execute bioinformatics sub-modules."""

    def test_sequential_no_cache_runs_bioinformatics_modules(self, monkeypatch):
        from types import SimpleNamespace

        import med_research.cli as cli_mod
        from med_research.cli import cmd_run_all

        captured: list[str] = []

        def fake_run_all_module(module_id, _args):
            captured.append(module_id)
            return 0

        monkeypatch.setattr(cli_mod, "_warn_config_gaps", lambda _d: False)
        monkeypatch.setattr(cli_mod, "_run_all_module", fake_run_all_module)

        args = SimpleNamespace(
            disease="sle",
            parallel=False,
            sequential=False,
            full=False,
            skip_trials=False,
            skip_ml=False,
            skip_synergy=False,
            no_cache=True,
            export_html=False,
        )
        assert cmd_run_all(args) == 0
        for bio_id in ("gwas", "enrichment", "ppi"):
            assert bio_id in captured

    def test_run_all_module_forwards_no_cache_to_execute(self):
        from types import SimpleNamespace

        from med_research.cli import _run_all_module
        from med_research.pipeline.base import PipelineRunResult

        captured: dict = {}

        def fake_execute(module_id, disease_id, **kwargs):
            captured.update(kwargs)
            return PipelineRunResult(success=True, data={})

        args = SimpleNamespace(disease="ra", no_cache=True, export_html=False)
        with patch(
            "med_research.pipeline.dispatch.execute_module",
            side_effect=fake_execute,
        ):
            assert _run_all_module("gwas", args) == 0
        assert captured.get("use_cache") is False

    def test_cmd_run_all_sequential_returns_error_count(self, monkeypatch):
        from types import SimpleNamespace

        import med_research.cli as cli_mod
        from med_research.cli import cmd_run_all

        def fake_run_all_module(module_id, _args):
            return 1 if module_id == "gwas" else 0

        monkeypatch.setattr(cli_mod, "_warn_config_gaps", lambda _d: False)
        monkeypatch.setattr(cli_mod, "_run_all_module", fake_run_all_module)
        monkeypatch.setattr(cli_mod, "rate_limited_sleep", lambda _s: None)

        args = SimpleNamespace(
            disease="sle",
            parallel=False,
            sequential=False,
            full=False,
            skip_trials=False,
            skip_ml=False,
            skip_synergy=False,
            no_cache=False,
            export_html=False,
        )
        assert cmd_run_all(args) == 1

    def test_cmd_run_all_catches_module_exceptions(self, monkeypatch):
        from types import SimpleNamespace

        import med_research.cli as cli_mod
        from med_research.cli import cmd_run_all

        def exploding_run_all_module(module_id, _args):
            if module_id == "knowledge_graph":
                raise RuntimeError("simulated failure")
            return 0

        monkeypatch.setattr(cli_mod, "_warn_config_gaps", lambda _d: False)
        monkeypatch.setattr(cli_mod, "_run_all_module", exploding_run_all_module)
        monkeypatch.setattr(cli_mod, "rate_limited_sleep", lambda _s: None)

        args = SimpleNamespace(
            disease="sle",
            parallel=False,
            sequential=False,
            full=False,
            skip_trials=False,
            skip_ml=False,
            skip_synergy=False,
            no_cache=False,
            export_html=False,
        )
        assert cmd_run_all(args) == 1
    """Coverage for diseases.coverage_report helpers."""

    def test_build_coverage_report_has_fingerprint(self):
        from med_research.diseases.coverage_report import build_coverage_report

        report = build_coverage_report("ra", modules=("kg", "repurposing"))
        assert report["disease_id"] == "ra"
        assert "fingerprint" in report
        assert "modules" in report
        assert "kg" in report["modules"]


class TestCliCoverageBoost:
    """Lightweight CLI handler smoke tests for uncovered cmd_* paths."""

    def test_cli_diseases_command(self):
        from tests.cli_helpers import run_cli_command

        assert run_cli_command("diseases") == 0

    def test_cli_modules_json(self):
        import json
        from types import SimpleNamespace

        from med_research.cli import cmd_modules
        from med_research.pipeline.registry import list_modules

        list_modules()  # warm adapter imports before any stdout redirection
        captured: list[str] = []

        def fake_print(value, **_kwargs):
            captured.append(value)

        with patch("builtins.print", fake_print):
            assert cmd_modules(SimpleNamespace(json=True)) == 0
        data = json.loads(captured[0])
        assert "knowledge_graph" in data

    def test_cli_cache_stats(self):
        from tests.cli_helpers import run_cli_command

        assert run_cli_command("cache", "stats") == 0

    def test_cli_disease_validate_ra(self):
        from tests.cli_helpers import run_cli_command

        assert run_cli_command("disease", "validate", "ra") == 0

    def test_cli_repurpose_with_mock_dispatch(self):
        from med_research.pipeline.base import PipelineRunResult
        from tests.cli_helpers import run_cli_command

        ok = PipelineRunResult(success=True, data=[])
        with patch("med_research.cli._dispatch", return_value=ok), patch(
            "med_research.pipeline.drug_repurposing.engine.analyze"
        ), patch(
            "med_research.pipeline.drug_repurposing.engine.print_top_candidates"
        ):
            assert run_cli_command("repurpose", "--disease", "ra", "--top", "5") == 0

    def test_cli_kg_with_mock_dispatch(self):
        from med_research.pipeline.base import PipelineRunResult
        from tests.cli_helpers import run_cli_command

        graph = MagicMock()
        graph.number_of_nodes.return_value = 10
        graph.number_of_edges.return_value = 20
        ok = PipelineRunResult(success=True, data=graph)
        with patch("med_research.cli._dispatch", return_value=ok), patch(
            "med_research.pipeline.knowledge_graph.builder.export_for_web"
        ):
            assert run_cli_command("kg", "--disease", "ra") == 0

    def test_cli_bioinformatics_skips_with_mock_dispatch(self):
        from med_research.pipeline.base import PipelineRunResult
        from tests.cli_helpers import run_cli_command

        ok = PipelineRunResult(success=True, data={})
        with patch("med_research.cli._dispatch", return_value=ok):
            assert run_cli_command(
                "bioinformatics",
                "--disease",
                "ra",
                "--skip-gwas",
                "--skip-enrichment",
                "--skip-ppi",
            ) == 0

    def test_cli_bioinformatics_no_cache_runs_all(self):
        from med_research.pipeline.base import PipelineRunResult
        from tests.cli_helpers import run_cli_command

        ok = PipelineRunResult(success=True, data={})
        with patch("med_research.cli._dispatch", return_value=ok) as mock_dispatch:
            assert run_cli_command("bioinformatics", "--disease", "ra", "--no-cache") == 0
        assert mock_dispatch.call_count == 3
        for call in mock_dispatch.call_args_list:
            assert call.kwargs.get("use_cache") is False

    def test_cli_more_dispatch_commands_with_mocks(self):
        from med_research.pipeline.base import PipelineRunResult
        from tests.cli_helpers import run_cli_command

        ok_list = PipelineRunResult(success=True, data=[])
        ok_dict = PipelineRunResult(
            success=True,
            data={
                "results": {"gene_coverage": {}, "coverage": {}},
                "entities": {"genes": {}},
                "candidates": [],
            },
        )
        ok_screen = PipelineRunResult(success=True, data={"coverage": {}, "results_per_target": {}})
        ok_trials = PipelineRunResult(success=True, data={"stats": {}, "kg_crossref": {}})
        ok_ml = PipelineRunResult(success=True, data={"predictions": []})

        with patch("med_research.cli._dispatch") as mock_dispatch:
            mock_dispatch.side_effect = [
                ok_dict,
                ok_screen,
                ok_trials,
                ok_ml,
                ok_list,
            ]
            with patch(
                "med_research.pipeline.literature_mining.miner.print_summary"
            ), patch(
                "med_research.pipeline.virtual_screening.screening.print_summary"
            ), patch(
                "med_research.pipeline.clinical_trials.tracker.print_summary"
            ), patch(
                "med_research.pipeline.ml_predictor.predictor.print_summary"
            ), patch(
                "med_research.pipeline.drug_synergy.engine.analyze"
            ), patch(
                "med_research.pipeline.drug_synergy.engine.print_top_pairs"
            ):
                assert run_cli_command("literature", "--disease", "ra", "--max", "5") == 0
                assert run_cli_command("screening", "--disease", "ra", "--top", "5") == 0
                assert run_cli_command("trials", "--disease", "ra", "--top", "5") == 0
                assert run_cli_command("ml", "--disease", "ra", "--top", "5") == 0
                assert run_cli_command("synergy", "--disease", "ra", "--top", "5") == 0
        assert mock_dispatch.call_count == 5

    def test_cli_safety_network_expression_cart_with_mocks(self, monkeypatch):
        import med_research.cli as cli_mod
        import med_research.pipeline.network_pharmacology.analyzer as network_analyzer
        from med_research.cli import cmd_cart, cmd_expression, cmd_network, cmd_safety
        from med_research.pipeline.base import PipelineRunResult
        from tests.cli_helpers import parse_cli_args

        network_data = {
            "graph_metrics": {
                "n_nodes": 0,
                "n_edges": 0,
                "density": 0.0,
                "n_components": 0,
                "diameter": 0,
                "avg_shortest_path": 0.0,
                "avg_clustering": 0.0,
                "assortativity": 0.0,
            },
            "centrality": {"pagerank": [], "eigenvector": []},
            "bridge_nodes": [],
            "communities": {
                "algorithm": "louvain",
                "modularity": 0.0,
                "n_communities": 0,
                "communities": [],
            },
        }

        def fake_dispatch(module_id, _disease, _args, **kwargs):
            if module_id == "network_pharmacology":
                return PipelineRunResult(success=True, data=network_data)
            return PipelineRunResult(success=True, data=[])

        monkeypatch.setattr(cli_mod, "_dispatch", fake_dispatch)
        monkeypatch.setattr(network_analyzer, "print_analysis", lambda *a, **k: None)
        monkeypatch.setattr(
            "med_research.pipeline.adverse_events.profiler.get_safety_summary",
            lambda **kwargs: {"total_drugs": 0, "avg_safety_score": 0.0},
        )
        monkeypatch.setattr(
            "med_research.pipeline.adverse_events.profiler.print_analysis",
            lambda *a, **k: None,
        )
        monkeypatch.setattr(
            "med_research.pipeline.gene_expression.correlator.analyze",
            lambda *a, **k: None,
        )
        monkeypatch.setattr(
            "med_research.pipeline.gene_expression.correlator.print_top_correlations",
            lambda *a, **k: None,
        )
        monkeypatch.setattr(
            "med_research.pipeline.car_t_predictor.predictor.print_top_genes",
            lambda *a, **k: None,
        )
        monkeypatch.setattr(
            "med_research.pipeline.car_t_predictor.predictor.analyze",
            lambda *a, **k: None,
        )

        assert cmd_safety(parse_cli_args("safety", "--disease", "ra")) == 0
        assert cmd_network(parse_cli_args("network", "--disease", "ra")) == 0
        assert cmd_expression(parse_cli_args("expression", "--disease", "ra", "--top", "5")) == 0
        assert cmd_cart(parse_cli_args("cart", "--disease", "ra")) == 0

    def test_cli_evidence_stack_with_mocks(self, tmp_path):
        from datetime import datetime, timezone

        from med_research.pipeline.base import PipelineRunResult
        from med_research.pipeline.evidence_workspace.schemas import (
            EvidenceDossier,
            ResearchRequest,
        )
        from tests.cli_helpers import run_cli_command

        ok = PipelineRunResult(success=True, data={})
        request = ResearchRequest(question="RA drug targets", disease_id="ra")
        dossier = EvidenceDossier(
            run_id="ew-test",
            request=request,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            warnings=["coverage gap"],
        )
        json_path = tmp_path / "dossier.json"
        html_path = tmp_path / "dossier.html"

        with patch("med_research.cli._dispatch") as mock_dispatch:
            mock_dispatch.side_effect = [
                PipelineRunResult(success=True, data=dossier),
                ok,
                ok,
                ok,
                PipelineRunResult(success=True, data={"diff": {}}),
                ok,
                ok,
                ok,
            ]
            with patch(
                "med_research.pipeline.biomarker_discovery.discover.analyze"
            ), patch(
                "med_research.pipeline.biomarker_discovery.discover.print_top_biomarkers"
            ), patch(
                "med_research.pipeline.cross_disease.analyzer.analyze"
            ), patch(
                "med_research.pipeline.cross_disease.analyzer.print_top_drugs"
            ), patch(
                "med_research.pipeline.cross_disease.analyzer.print_repurposing"
            ), patch(
                "med_research.pipeline.evidence.monitor.list_snapshots",
                return_value=[tmp_path / "snap1.json"],
            ), patch(
                "med_research.pipeline.evidence.monitor.print_diff_summary"
            ):
                assert run_cli_command(
                    "workspace",
                    "--question",
                    "RA drug targets",
                    "--disease",
                    "ra",
                    "--json",
                    str(json_path),
                    "--html",
                    str(html_path),
                ) == 0
                assert json_path.is_file()
                assert html_path.is_file()
                assert run_cli_command("semantic", "--disease", "ra", "--top", "5") == 0
                assert run_cli_command("evidence", "--disease", "ra", "--max", "5") == 0
                assert run_cli_command("extractor", "--disease", "ra", "--max", "5") == 0
                assert run_cli_command("monitor", "--list") == 0
                assert run_cli_command(
                    "monitor", "--disease", "ra", "--diff", "--max", "5"
                ) == 0
                assert run_cli_command("monitor", "--disease", "ra", "--max", "5") == 0
                assert run_cli_command("biomarker", "--disease", "ra", "--top", "5") == 0
                assert run_cli_command("cross-disease", "--disease", "ra", "--top", "5") == 0
        assert mock_dispatch.call_count == 8

    def test_cli_safety_drug_profile_paths(self):
        from tests.cli_helpers import run_cli_command

        with patch(
            "med_research.pipeline.adverse_events.profiler.get_drug_profile",
            return_value=None,
        ):
            assert run_cli_command("safety", "--disease", "ra", "--drug", "methotrexate") == 1
        profile = {
            "drug_name": "Methotrexate",
            "composite_safety_score": 7.5,
            "disease_symptom_overlap_score": 2,
            "severity_burden_score": 3,
            "chronic_use_safety_score": 8,
            "disease_specific_risk_score": 4,
            "black_box_warnings": [],
            "disease_overlap_ae": [],
        }
        with patch(
            "med_research.pipeline.adverse_events.profiler.get_drug_profile",
            return_value=profile,
        ):
            assert run_cli_command("safety", "--disease", "ra", "--drug", "methotrexate") == 0

    def test_cli_cache_cleanup_and_migrate(self):
        from tests.cli_helpers import run_cli_command

        with patch("med_research.cache.CacheManager.cleanup", return_value=2):
            assert run_cli_command("cache", "cleanup") == 0
        with patch(
            "med_research.cache.migrate_legacy_caches",
            return_value={
                "total": {"migrated": 1, "skipped": 0, "error": 0},
                "namespaces": {"pubmed": {"migrated": 1, "skipped": 0}},
            },
        ):
            assert run_cli_command("cache", "migrate") == 0

    def test_cli_cache_clear(self):
        from tests.cli_helpers import run_cli_command

        with patch("med_research.cache.CacheManager.clear", return_value=4):
            assert run_cli_command("cache", "clear") == 0

    def test_cli_modules_text_mode(self):
        from types import SimpleNamespace

        from med_research.cli import cmd_modules
        from med_research.pipeline.registry import list_modules

        list_modules()
        assert cmd_modules(SimpleNamespace(json=False)) == 0

    def test_cli_cart_blocked_when_coverage_missing(self, monkeypatch):
        import med_research.pipeline.car_t_predictor.predictor as cart_predictor
        from med_research.cli import cmd_cart
        from med_research.diseases.coverage import ModuleCoverage
        from med_research.pipeline.base import PipelineRunResult
        from tests.cli_helpers import parse_cli_args

        blocked = ModuleCoverage(
            disease_id="ra",
            module="car_t_predictor",
            level="unsupported",
            status="blocked",
            missing_inputs=["expression matrix"],
        )
        monkeypatch.setattr(cart_predictor, "last_coverage", blocked)
        monkeypatch.setattr(
            "med_research.cli._dispatch",
            lambda *a, **k: PipelineRunResult(success=True, data=[]),
        )
        assert cmd_cart(parse_cli_args("cart", "--disease", "ra")) == 1


class TestExportRouterUnit:
    """Direct tests for export router helpers and edge cases."""

    def test_find_results_file_returns_none_when_missing(self):
        from med_research.web.routers.export import _find_results_file

        assert _find_results_file("nonexistent_results_xyz.json") is None

    def test_all_pipeline_data_dirs_skips_missing_root(self, monkeypatch):
        from med_research.web.routers import export as export_mod

        monkeypatch.setattr(export_mod, "PIPELINE_DIR", export_mod.Path("/nonexistent/pipeline"))
        assert export_mod._all_pipeline_data_dirs() == []

    def test_export_corrupt_json_returns_500(self, client, tmp_path, monkeypatch):
        from med_research.web.routers import export as export_mod

        bad_file = tmp_path / "candidates.json"
        bad_file.write_text("{not-json", encoding="utf-8")
        monkeypatch.setattr(
            export_mod,
            "_find_results_file",
            lambda fname: bad_file if fname == "candidates.json" else None,
        )
        resp = client.get("/api/export/json/repurpose")
        assert resp.status_code == 500
        assert "corrupt" in resp.json()["detail"].lower()

    def test_export_report_not_found(self, client, monkeypatch):
        from med_research.web.routers import export as export_mod

        monkeypatch.setattr(export_mod, "PIPELINE_DIR", export_mod.Path("/nonexistent/pipeline"))
        resp = client.get("/api/export/report/repurpose")
        assert resp.status_code == 404

    def test_export_raw_unknown_module(self, client):
        resp = client.get("/api/export/raw/unknown_module_xyz")
        assert resp.status_code == 404


class TestJobsRouterHelpers:
    """Unit tests for jobs router parsing and validation helpers."""

    def test_validate_job_id_rejects_invalid(self):
        from fastapi import HTTPException

        from med_research.web.routers.jobs import _validate_job_id

        with pytest.raises(HTTPException) as exc_info:
            _validate_job_id("not-a-uuid")
        assert exc_info.value.status_code == 400

    def test_validate_job_id_accepts_uuid(self):
        from med_research.web.routers.jobs import _validate_job_id

        job_id = _validate_job_id("00000000-0000-0000-0000-000000000001")
        assert job_id == "00000000-0000-0000-0000-000000000001"

    def test_celery_backend_errors_includes_base_types(self):
        from med_research.web.routers.jobs import _celery_backend_errors

        errors = _celery_backend_errors()
        assert AttributeError in errors
        assert OSError in errors
        assert ConnectionError in errors

    def test_safe_result_state_returns_none_on_backend_error(self):
        from med_research.web.routers.jobs import _safe_result_state

        class BrokenResult:
            @property
            def state(self):
                raise AttributeError("backend down")

        assert _safe_result_state(BrokenResult()) is None

    def test_submit_gwas_job_mocked(self, client):
        with patch("med_research.web.routers.jobs.task_run_gwas") as mock_task:
            mock_task.delay.return_value.id = "00000000-0000-0000-0000-000000000010"
            resp = client.post(
                "/api/jobs/gwas",
                params={"max_studies": 5, "no_cache": True, "disease_id": "ra"},
            )
        assert resp.status_code == 200
        mock_task.delay.assert_called_once_with(
            max_studies=5, no_cache=True, disease_id="ra"
        )

    def test_submit_enrichment_job_mocked(self, client):
        with patch("med_research.web.routers.jobs.task_run_enrichment") as mock_task:
            mock_task.delay.return_value.id = "00000000-0000-0000-0000-000000000011"
            resp = client.post(
                "/api/jobs/enrichment",
                params={"untargeted_only": True, "no_cache": True, "disease_id": "ra"},
            )
        assert resp.status_code == 200
        mock_task.delay.assert_called_once_with(
            untargeted_only=True, no_cache=True, disease_id="ra"
        )

    def test_submit_ppi_job_mocked(self, client):
        with patch("med_research.web.routers.jobs.task_run_ppi") as mock_task:
            mock_task.delay.return_value.id = "00000000-0000-0000-0000-000000000012"
            resp = client.post(
                "/api/jobs/ppi",
                params={"confidence": 0.7, "no_cache": True, "disease_id": "ra"},
            )
        assert resp.status_code == 200
        mock_task.delay.assert_called_once_with(
            confidence=0.7, no_cache=True, disease_id="ra"
        )

    def test_submit_literature_job_mocked(self, client):
        with patch("med_research.web.routers.jobs.task_run_literature") as mock_task:
            mock_task.delay.return_value.id = "00000000-0000-0000-0000-000000000013"
            resp = client.post(
                "/api/jobs/literature",
                params={"max_articles": 10, "targeted": True, "disease_id": "ra"},
            )
        assert resp.status_code == 200
        mock_task.delay.assert_called_once_with(
            max_articles=10, targeted=True, no_cache=False, disease_id="ra"
        )

    def test_submit_screening_job_mocked(self, client):
        with patch("med_research.web.routers.jobs.task_run_screening") as mock_task:
            mock_task.delay.return_value.id = "00000000-0000-0000-0000-000000000014"
            resp = client.post(
                "/api/jobs/screening",
                params={"gene_id": "BTK", "top_n": 5, "disease_id": "ra"},
            )
        assert resp.status_code == 200
        mock_task.delay.assert_called_once_with(
            gene_id="BTK", top_n=5, use_vina=False, disease_id="ra"
        )

    def test_submit_trials_job_mocked(self, client):
        with patch("med_research.web.routers.jobs.task_run_trials") as mock_task:
            mock_task.delay.return_value.id = "00000000-0000-0000-0000-000000000015"
            resp = client.post(
                "/api/jobs/trials",
                params={"max_trials": 20, "query": "RA", "no_cache": True, "disease_id": "ra"},
            )
        assert resp.status_code == 200
        mock_task.delay.assert_called_once_with(
            max_trials=20, query="RA", no_cache=True, disease_id="ra"
        )

    def test_submit_ml_synergy_safety_mocked(self, client):
        with patch("med_research.web.routers.jobs.task_run_ml") as mock_ml:
            mock_ml.delay.return_value.id = "00000000-0000-0000-0000-000000000016"
            ml_resp = client.post("/api/jobs/ml", params={"top_n": 5, "disease_id": "ra"})
            assert ml_resp.status_code == 200
            mock_ml.delay.assert_called_once_with(top_n=5, no_shap=False, disease_id="ra")

        with patch("med_research.web.routers.jobs.task_run_synergy") as mock_synergy:
            mock_synergy.delay.return_value.id = "00000000-0000-0000-0000-000000000017"
            synergy_resp = client.post("/api/jobs/synergy", params={"top_n": 10, "disease_id": "ra"})
            assert synergy_resp.status_code == 200
            mock_synergy.delay.assert_called_once_with(top_n=10, disease_id="ra")

        with patch("med_research.web.routers.jobs.task_run_safety") as mock_safety:
            mock_safety.delay.return_value.id = "00000000-0000-0000-0000-000000000018"
            safety_resp = client.post(
                "/api/jobs/safety",
                params={"drug_id": "belimumab", "disease_id": "ra"},
            )
            assert safety_resp.status_code == 200
            mock_safety.delay.assert_called_once_with(drug_id="belimumab", disease_id="ra")

    def test_get_job_status_success_mocked(self, client):
        with patch("med_research.web.routers.jobs.AsyncResult") as mock_async:
            mock_result = MagicMock()
            mock_result.state = "SUCCESS"
            mock_result.result = {"ok": True}
            mock_async.return_value = mock_result
            resp = client.get("/api/jobs/00000000-0000-0000-0000-000000000099")
        assert resp.status_code == 200
        assert resp.json()["status"] == "SUCCESS"
        assert resp.json()["result"] == {"ok": True}

    def test_get_job_status_failure_mocked(self, client):
        with patch("med_research.web.routers.jobs.AsyncResult") as mock_async:
            mock_result = MagicMock()
            mock_result.state = "FAILURE"
            mock_result.info = "task exploded"
            mock_async.return_value = mock_result
            resp = client.get("/api/jobs/00000000-0000-0000-0000-000000000088")
        assert resp.status_code == 200
        assert resp.json()["error"] == "task exploded"

    def test_get_job_status_progress_mocked(self, client):
        with patch("med_research.web.routers.jobs.AsyncResult") as mock_async:
            mock_result = MagicMock()
            mock_result.state = "PROGRESS"
            mock_result.info = {"percent": 50, "message": "halfway"}
            mock_async.return_value = mock_result
            resp = client.get("/api/jobs/00000000-0000-0000-0000-000000000077")
        assert resp.status_code == 200
        assert resp.json()["progress"] == {"percent": 50, "message": "halfway"}


class TestSharedServicesUnit:
    """Unit tests for shared_services with mocked registry dispatch."""

    def test_run_literature_empty_crossref(self):
        with patch(
            "med_research.web.services.shared_services.dispatch_sync_module",
            return_value={"results": {}},
        ), patch(
            "med_research.web.services.shared_services.get_kg_genes",
            return_value={},
        ), patch(
            "med_research.web.services.shared_services.get_candidates",
            return_value=[],
        ):
            from med_research.web.services.shared_services import run_literature

            result = run_literature(max_articles=5, disease_id="ra")
        assert result["total_articles"] == 0
        assert result["articles"] == []
        assert result["status"] == "ready"

    def test_run_literature_with_gene_coverage(self):
        crossref = {
            "article_matches": [{"pmid": "1", "title": "test"}],
            "gene_coverage": {"BTK": {"articles": 2, "supporting_count": 1, "coverage_score": 50}},
            "candidate_support": [],
        }
        with patch(
            "med_research.web.services.shared_services.dispatch_sync_module",
            return_value={"results": crossref},
        ), patch(
            "med_research.web.services.shared_services.get_kg_genes",
            return_value={"BTK": {"name": "BTK"}},
        ), patch(
            "med_research.web.services.shared_services.get_candidates",
            return_value=[],
        ):
            from med_research.web.services.shared_services import run_literature

            result = run_literature(max_articles=5, disease_id="ra", targeted=True)
        assert result["total_articles"] == 1
        assert result["gene_coverage"][0]["gene_id"] == "BTK"

    def test_run_screening_blocked_raises(self):
        from med_research.exceptions import ModuleNotAvailableError

        with patch(
            "med_research.web.services.shared_services.module_coverage",
        ) as mock_cov:
            mock_cov.return_value.is_runnable = False
            mock_cov.return_value.limitations = ["missing genes"]
            from med_research.web.services.shared_services import run_screening

            with pytest.raises(ModuleNotAvailableError):
                run_screening(disease_id="ra")

    def test_run_trials_uses_disease_query(self):
        with patch(
            "med_research.web.services.shared_services.dispatch_sync_module",
            return_value={
                "trials": [{"moa_category": "mAb"}],
                "stats": {"phase_counts": {"III": 1}, "top_sponsors": []},
                "kg_crossref": {},
                "coverage": {},
                "status": "ready",
            },
        ):
            from med_research.web.services.shared_services import run_trials

            result = run_trials(max_trials=10, disease_id="ra")
        assert result["total_trials"] == 1
        assert result["moa_distribution"]["mAb"] == 1

    def test_run_ml_prediction_blocked_raises(self):
        from med_research.exceptions import ModuleNotAvailableError

        with patch(
            "med_research.web.services.shared_services.module_coverage",
        ) as mock_cov:
            mock_cov.return_value.is_runnable = False
            mock_cov.return_value.limitations = ["missing genes"]
            from med_research.web.services.shared_services import run_ml_prediction

            with pytest.raises(ModuleNotAvailableError):
                run_ml_prediction(disease_id="ra")

    def test_run_ml_prediction_with_results(self):
        with patch(
            "med_research.web.services.shared_services.module_coverage",
        ) as mock_cov, patch(
            "med_research.web.services.shared_services.dispatch_sync_module",
            return_value={
                "predictions": [{"gene_id": "BTK", "druggability_score": 0.9}],
                "model_metrics": {"cv_auc_mean": 0.8, "accuracy": 0.75},
                "feature_importance": {"degree": 0.5},
            },
        ):
            mock_cov.return_value.is_runnable = True
            mock_cov.return_value.level = "full"
            mock_cov.return_value.to_dict.return_value = {"level": "full"}
            from med_research.web.services.shared_services import run_ml_prediction

            result = run_ml_prediction(top_n=5, disease_id="ra")
        assert len(result["predictions"]) == 1
        assert result["predictions"][0]["rank"] == 1
        assert result["top_features"][0]["feature"] == "degree"

    def test_run_ml_prediction_error_raises(self):
        from med_research.exceptions import ModuleNotAvailableError

        with patch(
            "med_research.web.services.shared_services.module_coverage",
        ) as mock_cov, patch(
            "med_research.web.services.shared_services.dispatch_sync_module",
            return_value={"error": "model unavailable"},
        ):
            mock_cov.return_value.is_runnable = True
            mock_cov.return_value.level = "full"
            mock_cov.return_value.to_dict.return_value = {"level": "full"}
            from med_research.web.services.shared_services import run_ml_prediction

            with pytest.raises(ModuleNotAvailableError, match="model unavailable"):
                run_ml_prediction(disease_id="ra")

    def test_run_literature_numeric_gene_coverage(self):
        crossref = {
            "article_matches": [{"pmid": "1"}],
            "gene_coverage": {"BTK": 3},
            "candidate_support": [],
        }
        with patch(
            "med_research.web.services.shared_services.dispatch_sync_module",
            return_value={"results": crossref},
        ), patch(
            "med_research.web.services.shared_services.get_kg_genes",
            return_value={"BTK": {"name": "BTK"}},
        ), patch(
            "med_research.web.services.shared_services.get_candidates",
            return_value=[],
        ):
            from med_research.web.services.shared_services import run_literature

            result = run_literature(max_articles=5, disease_id="ra")
        assert result["gene_coverage"][0]["article_count"] == 3

    def test_run_screening_success_formats_targets(self):
        untargeted = {"untargeted_genes": [{"id": "BTK"}]}
        screening_results = {
            "results_per_target": {
                "BTK": {
                    "gene_info": {"name": "BTK", "category": "kinase"},
                    "top_compounds": [
                        {
                            "id": "drug1",
                            "name": "Drug 1",
                            "composite_score": 8.0,
                            "binding_estimate": 7.0,
                            "druglikeness": 6.0,
                            "target_complementarity": 5.0,
                            "similarity_score": 4.0,
                            "novelty_score": 3.0,
                            "tier": "tier1",
                            "gene_id": "BTK",
                            "gene_name": "BTK",
                            "type": "small_molecule",
                        }
                    ],
                    "total_screened": 100,
                    "mean_score": 5.0,
                }
            },
            "stats": {
                "compounds_screened": 100,
                "total_pairings": 200,
                "tier1_count": 1,
                "tier2_count": 0,
                "vina_available": True,
                "rdkit_available": True,
            },
            "status": "ready",
            "disease_id": "ra",
        }

        def dispatch_side_effect(_module_id, _disease_id, **kwargs):
            if kwargs.get("operation") == "untargeted_genes":
                return untargeted
            return screening_results

        with patch(
            "med_research.web.services.shared_services.module_coverage",
        ) as mock_cov, patch(
            "med_research.web.services.shared_services.dispatch_sync_module",
            side_effect=dispatch_side_effect,
        ):
            mock_cov.return_value.is_runnable = True
            mock_cov.return_value.to_dict.return_value = {"level": "full"}
            from med_research.web.services.shared_services import run_screening

            result = run_screening(top_n=5, disease_id="ra")
        assert len(result["targets"]) == 1
        assert result["targets"][0]["gene_id"] == "BTK"
        assert result["vina_available"] is True

    def test_run_screening_with_explicit_gene_id(self):
        screening_results = {
            "results_per_target": {
                "BTK": {
                    "gene_info": {"name": "BTK", "category": "kinase"},
                    "top_compounds": [],
                    "total_screened": 0,
                    "mean_score": 0.0,
                }
            },
            "stats": {},
            "status": "ready",
            "disease_id": "ra",
        }
        with patch(
            "med_research.web.services.shared_services.module_coverage",
        ) as mock_cov, patch(
            "med_research.web.services.shared_services.dispatch_sync_module",
            return_value=screening_results,
        ):
            mock_cov.return_value.is_runnable = True
            mock_cov.return_value.to_dict.return_value = {"level": "full"}
            from med_research.web.services.shared_services import run_screening

            result = run_screening(gene_id="BTK", disease_id="ra")
        assert result["targets"][0]["gene_id"] == "BTK"


class TestJobsWebSocketUnit:
    """WebSocket job streaming with mocked Celery backend (no Redis)."""

    def test_websocket_success_terminal_message(self, client):
        with patch("med_research.web.routers.jobs.AsyncResult") as mock_async:
            mock_result = MagicMock()
            mock_result.state = "SUCCESS"
            mock_result.result = {"done": True}
            mock_result.info = None
            mock_result.date_done = True
            mock_async.return_value = mock_result

            with client.websocket_connect(
                "/api/jobs/00000000-0000-0000-0000-000000000050/ws"
            ) as ws:
                msg = ws.receive_json()
        assert msg["status"] == "SUCCESS"
        assert msg["result"] == {"done": True}

    def test_websocket_failure_terminal_message(self, client):
        with patch("med_research.web.routers.jobs.AsyncResult") as mock_async:
            mock_result = MagicMock()
            mock_result.state = "FAILURE"
            mock_result.info = "task failed"
            mock_result.date_done = True
            mock_async.return_value = mock_result

            with client.websocket_connect(
                "/api/jobs/00000000-0000-0000-0000-000000000051/ws"
            ) as ws:
                msg = ws.receive_json()
        assert msg["status"] == "FAILURE"
        assert msg["error"] == "task failed"

    def test_websocket_backend_unavailable(self, client):
        with patch("med_research.web.routers.jobs.AsyncResult") as mock_async:
            class BrokenResult:
                @property
                def state(self):
                    raise AttributeError("no backend")

            mock_async.return_value = BrokenResult()

            with client.websocket_connect(
                "/api/jobs/00000000-0000-0000-0000-000000000052/ws"
            ) as ws:
                msg = ws.receive_json()
        assert msg["status"] == "ERROR"
        assert "backend" in msg["error"].lower()


class TestExportRouterExtended:
    """Additional export router coverage for happy paths."""

    def test_export_report_html_success(self, client, tmp_path, monkeypatch):
        from med_research.web.routers import export as export_mod

        report_dir = tmp_path / "drug_repurposing" / "data"
        report_dir.mkdir(parents=True)
        report_file = report_dir / "report.html"
        report_file.write_text("<html>report</html>", encoding="utf-8")
        monkeypatch.setattr(export_mod, "PIPELINE_DIR", tmp_path)

        resp = client.get("/api/export/report/repurpose")
        assert resp.status_code == 200
        assert "report" in resp.text

    def test_export_report_uses_module_root_fallback(self, client, tmp_path, monkeypatch):
        from med_research.web.routers import export as export_mod

        module_root = tmp_path / "car_t_predictor"
        module_root.mkdir()
        (module_root / "report.html").write_text("<html>cart</html>", encoding="utf-8")
        monkeypatch.setattr(export_mod, "PIPELINE_DIR", tmp_path)

        resp = client.get("/api/export/report/cart")
        assert resp.status_code == 200

    def test_list_export_modules_marks_availability(self, client, tmp_path, monkeypatch):
        from med_research.web.routers import export as export_mod

        data_dir = tmp_path / "drug_repurposing" / "data"
        data_dir.mkdir(parents=True)
        (data_dir / "candidates.json").write_text("{}", encoding="utf-8")
        monkeypatch.setattr(export_mod, "PIPELINE_DIR", tmp_path)

        resp = client.get("/api/export/modules")
        assert resp.status_code == 200
        repurpose = next(m for m in resp.json()["modules"] if m["module"] == "repurpose")
        assert repurpose["available"] is True


class TestBioinformaticsServiceUnit:
    """Unit tests for bioinformatics_service formatters."""

    def test_run_gwas_formats_response(self):
        raw = {
            "gwas_results": {
                "gene_associations": {
                    "BTK": {"n_studies": 3, "best_p_value": 1e-8, "studies": ["s1"]},
                },
                "total_studies_analyzed": 10,
                "total_associations": 5,
            },
            "crossref": {"validated": [], "novel": []},
            "coverage": {"level": "full"},
            "status": "ready",
        }
        with patch(
            "med_research.web.services.bioinformatics_service.dispatch_sync_module",
            return_value=raw,
        ), patch(
            "med_research.web.services.bioinformatics_service.get_kg_genes",
            return_value={"BTK": {"name": "BTK"}},
        ):
            from med_research.web.services.bioinformatics_service import run_gwas

            result = run_gwas(max_studies=5, no_cache=True, disease_id="ra")
        assert result["total_studies"] == 10
        assert result["top_hits"][0]["gene"] == "BTK"
        assert result["status"] == "ready"

    def test_run_enrichment_formats_libraries(self):
        raw = {
            "gene_list": [{"symbol": "BTK"}],
            "enrichment_results": {
                "GO": {
                    "library": "GO Biological Process",
                    "terms": [
                        {
                            "term": "immune response",
                            "p_value": 0.01,
                            "adj_p_value": 0.05,
                            "odds_ratio": 2.0,
                            "combined_score": 3.0,
                            "genes": ["BTK"],
                            "overlap": "1/10",
                        }
                    ],
                    "total_significant": 1,
                }
            },
            "kg_pathway_matches": {"type1-ifn": "match"},
            "coverage": {"level": "partial"},
        }
        with patch(
            "med_research.web.services.bioinformatics_service.dispatch_sync_module",
            return_value=raw,
        ):
            from med_research.web.services.bioinformatics_service import run_enrichment

            result = run_enrichment(untargeted_only=True, disease_id="ra")
        assert result["genes_analyzed"] == 1
        assert result["libraries"][0]["library"] == "GO Biological Process"
        assert result["status"] == "limited_coverage"

    def test_run_ppi_blocked_returns_empty_hubs(self):
        raw = {
            "status": "blocked",
            "hub_scores": [],
            "graph": {"nodes": [], "edges": []},
            "coverage": {"level": "none"},
        }
        with patch(
            "med_research.web.services.bioinformatics_service.dispatch_sync_module",
            return_value=raw,
        ):
            from med_research.web.services.bioinformatics_service import run_ppi

            result = run_ppi(confidence=0.5, disease_id="ra")
        assert result["top_hubs"] == []
        assert result["status"] == "blocked"

    def test_run_ppi_with_hub_scores(self):
        raw = {
            "hub_scores": [
                {
                    "symbol": "BTK",
                    "gene_id": "BTK",
                    "hub_score": 0.9,
                    "degree": 10,
                    "degree_centrality": 0.5,
                    "betweenness_centrality": 0.2,
                    "is_lupus_gene": True,
                    "is_seed": True,
                }
            ],
            "graph": {"nodes": [{"is_seed": True}], "edges": [{"a": 1}]},
            "crossref": {"hub_candidate_matches": ["x"], "hub_untargeted": ["y"]},
            "coverage": {"level": "full"},
        }
        with patch(
            "med_research.web.services.bioinformatics_service.dispatch_sync_module",
            return_value=raw,
        ):
            from med_research.web.services.bioinformatics_service import run_ppi

            result = run_ppi(confidence=0.6, disease_id="ra")
        assert len(result["top_hubs"]) == 1
        assert result["top_hubs"][0]["symbol"] == "BTK"
        assert result["hub_candidates"] == ["x"]


class TestKgServiceUnit:
    """Unit tests for kg_service graph helpers with a synthetic NetworkX graph."""

    @staticmethod
    def _sample_graph():
        import networkx as nx

        graph = nx.MultiDiGraph()
        graph.add_node(
            "BTK",
            type="gene",
            label="BTK",
            category="kinase",
            description="BTK kinase",
            odds_ratio=1.5,
            chromosome="10",
        )
        graph.add_node("belimumab", type="drug", label="belimumab")
        graph.add_node("type1-ifn", type="pathway", label="Type I IFN")
        graph.add_edge("belimumab", "BTK", key="t1", type="TARGETS", description="targets")
        graph.add_edge("BTK", "type1-ifn", key="p1", type="PARTICIPATES_IN", description="pathway")
        return graph

    def test_get_graph_stats_and_data(self):
        graph = self._sample_graph()
        with patch(
            "med_research.web.services.kg_service._load_graph",
            return_value=graph,
        ):
            from med_research.web.services.kg_service import get_graph_data, get_graph_stats

            stats = get_graph_stats(disease_id="ra")
            data = get_graph_data(disease_id="ra")
        assert stats["total_nodes"] == 3
        assert stats["node_types"]["gene"] == 1
        assert len(stats["untargeted_genes"]) >= 0
        assert len(data["elements"]) >= 4

    def test_node_detail_path_neighbors_and_search(self):
        graph = self._sample_graph()
        with patch(
            "med_research.web.services.kg_service._load_graph",
            return_value=graph,
        ):
            from med_research.web.services.kg_service import (
                get_neighbors,
                get_node_detail,
                get_shortest_path,
                search_nodes,
            )

            detail = get_node_detail("BTK", disease_id="ra")
            path = get_shortest_path("belimumab", "BTK", disease_id="ra")
            neighbors = get_neighbors("BTK", n_hops=1, disease_id="ra")
            multi_hop = get_neighbors("BTK", n_hops=2, disease_id="ra")
            results = search_nodes("btk", disease_id="ra")
        assert detail is not None
        assert detail["id"] == "BTK"
        assert path is not None
        assert path["path"] == ["belimumab", "BTK"]
        assert neighbors is not None
        assert neighbors["degree"] >= 1
        assert multi_hop is not None
        assert results[0]["id"] == "BTK"

    def test_network_pharmacology_dispatch_helpers(self):
        with patch(
            "med_research.web.services.kg_service.dispatch_sync_module",
            return_value={"metric": "betweenness", "nodes": []},
        ) as mock_dispatch:
            from med_research.web.services.kg_service import (
                run_centrality_analysis,
                run_community_detection,
            )

            centrality = run_centrality_analysis(metric="betweenness", top_n=5, disease_id="ra")
            communities = run_community_detection(disease_id="ra")
        assert centrality["metric"] == "betweenness"
        assert mock_dispatch.call_count == 2
        assert communities == {"metric": "betweenness", "nodes": []}


class TestSmallWebServicesUnit:
    """Unit tests for small disease-scoped web services."""

    def test_run_cart_analysis_tiers(self):
        results = [
            {"composite_score": 8.5, "gene_id": "BTK"},
            {"composite_score": 7.2, "gene_id": "IRF5"},
            {"composite_score": 5.5, "gene_id": "TLR7"},
        ]
        with patch(
            "med_research.web.services.car_t_service.module_coverage",
        ) as mock_cov, patch(
            "med_research.web.services.car_t_service.dispatch_sync_module",
            return_value=results,
        ), patch(
            "med_research.web.services.car_t_service.last_coverage",
            None,
        ):
            mock_cov.return_value.is_runnable = True
            mock_cov.return_value.to_dict.return_value = {"level": "full"}
            from med_research.web.services.car_t_service import run_cart_analysis

            payload = run_cart_analysis(top_n=2, disease_id="ra")
        assert payload["total_genes"] == 3
        assert payload["tier1_count"] == 1
        assert len(payload["genes"]) == 2

    def test_run_correlation_analysis_tiers(self):
        results = [
            {"composite_score": 8.0, "drug_id": "belimumab"},
            {"composite_score": 6.5, "drug_id": "rituximab"},
        ]
        with patch(
            "med_research.web.services.expression_service.module_coverage",
        ) as mock_cov, patch(
            "med_research.web.services.expression_service.dispatch_sync_module",
            return_value=results,
        ), patch(
            "med_research.web.services.expression_service.last_coverage",
            None,
        ):
            mock_cov.return_value.is_runnable = True
            mock_cov.return_value.to_dict.return_value = {"level": "partial"}
            from med_research.web.services.expression_service import run_correlation_analysis

            payload = run_correlation_analysis(top_n=5, disease_id="ra")
        assert payload["total_drugs"] == 2
        assert payload["status"] == "limited_coverage"


class TestAnalysisRouterUnit:
    """Fast router tests for analysis endpoints with mocked services."""

    def test_literature_router(self, client):
        payload = {
            "total_articles": 1,
            "queries_run": 1,
            "articles": [],
            "gene_coverage": [],
            "candidate_support": {},
            "coverage": {},
            "status": "ready",
        }
        with patch("med_research.web.routers.analysis.run_literature", return_value=payload):
            resp = client.get("/api/literature?max_articles=5&disease_id=ra")
        assert resp.status_code == 200
        assert resp.json()["total_articles"] == 1

    def test_screening_router(self, client):
        payload = {
            "targets": [],
            "compounds_screened": 0,
            "total_pairings": 0,
            "tier1_count": 0,
            "tier2_count": 0,
            "vina_available": False,
            "rdkit_available": False,
            "coverage": {},
            "status": "ready",
            "disease_id": "ra",
            "strategy_id": "",
            "strategy_fingerprint": "",
            "strategy_limitations": [],
        }
        with patch("med_research.web.routers.analysis.run_screening", return_value=payload):
            resp = client.get("/api/screening?top_n=5&disease_id=ra")
        assert resp.status_code == 200

    def test_trials_router(self, client):
        payload = {
            "total_trials": 0,
            "phase_distribution": {},
            "moa_distribution": {},
            "top_sponsors": [],
            "trials": [],
            "kg_crossref": {},
            "coverage": {},
            "status": "ready",
        }
        with patch("med_research.web.routers.analysis.run_trials", return_value=payload):
            resp = client.get("/api/trials?max_trials=10&disease_id=ra")
        assert resp.status_code == 200

    def test_ml_router(self, client):
        payload = {
            "predictions": [],
            "model_type": "XGBoost",
            "cross_val_auc": None,
            "accuracy": None,
            "top_features": [],
            "coverage": {},
            "status": "ready",
        }
        with patch("med_research.web.routers.analysis.run_ml_prediction", return_value=payload):
            resp = client.get("/api/ml/predict?top_n=5&disease_id=ra")
        assert resp.status_code == 200


class TestMiscRouterUnit:
    """Coverage for smaller routers via mocked services."""

    def test_biomarker_router(self, client):
        with patch(
            "med_research.web.routers.biomarker.run_biomarker_analysis",
            return_value={
                "biomarkers": [],
                "total_genes": 0,
                "avg_score": 0.0,
                "tier1_count": 0,
                "tier2_count": 0,
                "coverage": {},
                "status": "ready",
            },
        ):
            resp = client.get("/api/biomarker/discover?disease_id=ra")
        assert resp.status_code == 200

    def test_expression_router(self, client):
        with patch(
            "med_research.web.routers.expression.run_correlation_analysis",
            return_value={"drugs": [], "total_drugs": 0, "coverage": {}, "status": "ready"},
        ):
            resp = client.get("/api/expression/correlate?disease_id=ra")
        assert resp.status_code == 200

    def test_semantic_router(self, client):
        with patch(
            "med_research.web.routers.semantic.run_semantic_search",
            return_value={
                "results": [],
                "query": "lupus",
                "total_results": 0,
                "indexed_articles": 0,
                "coverage": {},
                "status": "ready",
            },
        ):
            resp = client.get("/api/semantic/search?q=lupus&disease_id=ra")
        assert resp.status_code == 200

    def test_monitor_router_endpoints(self, client):
        with patch(
            "med_research.web.services.monitor_service.run_snapshot",
            return_value={"snapshot_id": "s1"},
        ), patch(
            "med_research.web.routers.monitor.run_diff",
            return_value={"total_changes": 0, "alerts": [], "changes": {}},
        ), patch(
            "med_research.web.routers.monitor.run_status",
            return_value={"snapshots_available": 0, "last_snapshot": None},
        ):
            assert client.post("/api/monitor/snapshot").status_code == 200
            assert client.get("/api/monitor/diff").status_code == 200
            assert client.get("/api/monitor/status").status_code == 200

    def test_evidence_router_endpoints(self, client):
        gathered = {
            "query": "Systemic Lupus Erythematosus lupus",
            "sources_searched": ["pubmed"],
            "total_results": 0,
            "elapsed_seconds": 0.1,
            "results_by_source": {},
            "crossref": {},
            "all_results": [],
            "generated_at": "2026-01-01T00:00:00Z",
            "coverage": {},
            "status": "ready",
        }
        with patch(
            "med_research.web.routers.evidence.run_evidence_gather",
            return_value=gathered,
        ):
            resp = client.get("/api/evidence/gather?q=lupus&disease_id=sle")
        assert resp.status_code == 200
        assert resp.json()["total_results"] == 0

    def test_synergy_router(self, client):
        with patch(
            "med_research.web.routers.synergy.run_synergy",
            return_value={
                "pairs": [],
                "total_pairs": 0,
                "tier1_count": 0,
                "tier2_count": 0,
                "tier3_count": 0,
                "avg_score": 0.0,
                "max_score": 0.0,
                "coverage": {},
                "status": "ready",
            },
        ):
            resp = client.get("/api/synergy/pairs?top_n=5&disease_id=ra")
        assert resp.status_code == 200

    def test_jobs_websocket_progress_message(self, client):
        with patch("med_research.web.routers.jobs.AsyncResult") as mock_async:
            mock_result = MagicMock()
            states = ["PROGRESS", "SUCCESS"]
            mock_result.state = "PROGRESS"
            mock_result.info = {"percent": 40, "message": "working"}
            mock_result.date_done = None

            def advance_state():
                mock_result.state = states.pop(0) if states else "SUCCESS"
                mock_result.result = {"done": True}

            mock_async.return_value = mock_result

            with patch(
                "med_research.web.routers.jobs.asyncio.sleep",
                side_effect=lambda _: advance_state(),
            ), client.websocket_connect(
                "/api/jobs/00000000-0000-0000-0000-000000000053/ws"
            ) as ws:
                first = ws.receive_json()
                second = ws.receive_json()
        assert first["status"] == "PROGRESS"
        assert second["status"] == "SUCCESS"

    def test_submit_workspace_job_mocked(self, client):
        with patch("med_research.web.routers.jobs.task_run_workspace") as mock_task:
            mock_task.delay.return_value.id = "00000000-0000-0000-0000-000000000019"
            resp = client.post(
                "/api/jobs/workspace",
                json={
                    "question": "What drives lupus?",
                    "disease_id": "sle",
                    "sources": ["pubmed"],
                },
            )
        assert resp.status_code == 200
        assert resp.json()["module"] == "workspace"
        mock_task.delay.assert_called_once_with(
            disease_id="sle",
            question="What drives lupus?",
            sources=["pubmed"],
            date_from=None,
            date_to=None,
            candidate_type="both",
            max_evidence=50,
            enable_llm=True,
            researcher_id="anonymous",
        )

    def test_workspace_openapi_uses_registry_body_schema(self):
        operation = app.openapi()["paths"]["/api/jobs/workspace"]["post"]
        schema_ref = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
        schema_name = schema_ref.rsplit("/", 1)[-1]
        schema = app.openapi()["components"]["schemas"][schema_name]

        assert schema_name == "EvidenceWorkspaceRequest"
        assert schema["required"] == ["question"]
        assert schema["properties"]["question"]["minLength"] == 2
        assert schema["properties"]["max_evidence"]["maximum"] == 200
        source_items = schema["properties"]["sources"]["items"]
        assert set(source_items["enum"]) == {
            "pubmed",
            "clinical_trials",
            "gwas",
            "fda_labels",
        }


class TestMonitorServiceUnit:
    """Unit tests for monitor_service helpers."""

    def test_run_snapshot_and_diff(self):
        with patch(
            "med_research.web.services.monitor_service.dispatch_sync_module",
            return_value={"snapshot": {"id": "s1"}, "diff": {"changes": 1}},
        ):
            from med_research.web.services.monitor_service import run_diff, run_snapshot

            snapshot = run_snapshot(max_per_query=5, disease_id="ra")
            diff = run_diff(disease_id="ra")
        assert snapshot == {"id": "s1"}
        assert diff["changes"] == 1

    def test_run_status_lists_snapshots(self):
        snap = MagicMock()
        snap.stem = "snap1"
        with patch(
            "med_research.web.services.monitor_service.list_snapshots",
            return_value=[snap],
        ):
            from med_research.web.services.monitor_service import run_status

            status = run_status()
        assert status["snapshots_available"] == 1
        assert status["last_snapshot"] == "snap1"


class TestAnalysisTasksUnit:
    """Unit tests for Celery task helpers."""

    def test_make_progress_updates_task_state(self):
        from med_research.web.tasks.analysis_tasks import _make_progress

        task_self = MagicMock()
        progress = _make_progress(task_self)
        progress(50, "halfway")
        task_self.update_state.assert_called_once_with(
            state="PROGRESS",
            meta={"percent": 50, "message": "halfway"},
        )

    def test_dispatch_module_delegates_to_run_module_job(self):
        from med_research.web.tasks.analysis_tasks import _dispatch_module

        task_self = MagicMock()
        with patch(
            "med_research.web.services.registry_service.run_module_job",
            return_value={"ok": True},
        ) as mock_job:
            result = _dispatch_module(task_self, "gwas", "ra", max_studies=5)
        mock_job.assert_called_once()
        assert result == {"ok": True}

    def test_celery_module_tasks_dispatch(self):
        from med_research.web.tasks.analysis_tasks import (
            task_run_enrichment,
            task_run_gwas,
            task_run_literature,
            task_run_ml,
            task_run_trials,
        )

        with patch(
            "med_research.web.tasks.analysis_tasks._dispatch_module",
            return_value={"ok": True},
        ) as mock_dispatch:
            task_run_gwas.run(max_studies=5, disease_id="ra", no_cache=True)
            task_run_enrichment.run(untargeted_only=True, disease_id="ra")
            task_run_literature.run(max_articles=10, targeted=True, disease_id="ra")
            task_run_trials.run(max_trials=20, disease_id="ra", no_cache=True)
            task_run_ml.run(top_n=5, disease_id="ra")
        assert mock_dispatch.call_count == 5

    def test_remaining_celery_tasks_dispatch(self):
        from med_research.web.tasks.analysis_tasks import (
            task_run_module,
            task_run_ppi,
            task_run_safety,
            task_run_screening,
            task_run_synergy,
        )

        with patch(
            "med_research.web.tasks.analysis_tasks._dispatch_module",
            return_value={"ok": True},
        ) as mock_dispatch, patch(
            "med_research.web.services.registry_service.run_all_pipeline",
            return_value={"status": "success"},
        ):
            task_run_ppi.run(confidence=0.5, disease_id="ra")
            task_run_screening.run(gene_id="BTK", top_n=5, disease_id="ra")
            task_run_synergy.run(top_n=10, disease_id="ra")
            task_run_safety.run(drug_id="belimumab", disease_id="ra")
            task_run_module.run("gwas", "ra", max_studies=3)
        assert mock_dispatch.call_count == 5


class TestErrorHandlerIntegration:
    """Verify typed errors map to HTTP status codes via the FastAPI app."""

    def test_ml_endpoint_returns_409_when_blocked(self, client):
        from med_research.exceptions import ModuleNotAvailableError

        with patch(
            "med_research.web.routers.analysis.run_ml_prediction",
            side_effect=ModuleNotAvailableError("ml blocked"),
        ):
            resp = client.get("/api/ml/predict?disease_id=ra")
        assert resp.status_code == 409
        assert resp.json()["error_type"] == "ModuleNotAvailableError"

    def test_screening_endpoint_returns_409_when_blocked(self, client):
        from med_research.exceptions import ModuleNotAvailableError

        with patch(
            "med_research.web.routers.analysis.run_screening",
            side_effect=ModuleNotAvailableError("screening blocked"),
        ):
            resp = client.get("/api/screening?disease_id=ra")
        assert resp.status_code == 409


class TestCacheManagerUnit:
    """Basic CacheManager coverage for get/set/clear."""

    def test_cache_round_trip_and_clear(self, tmp_path):
        from med_research.cache import CacheManager

        cache = CacheManager(cache_dir=tmp_path, ttl_seconds=3600)
        cache.set("gwas", "ra|||studies", {"hits": [1]})
        assert cache.get("gwas", "ra|||studies") == {"hits": [1]}
        cache.clear("gwas")
        assert cache.get("gwas", "ra|||studies") is None

    def test_safe_key_filename_hashes_long_keys(self, tmp_path):
        from med_research.cache import CacheManager

        cache = CacheManager(cache_dir=tmp_path)
        long_key = "x" * 200
        filename = cache._safe_key_filename(long_key)
        assert len(filename) == 64


class TestAdditionalRouterUnit:
    """Extra router coverage for KG network, CAR-T, and safety endpoints."""

    def test_kg_centrality_and_communities(self, client):
        with patch(
            "med_research.web.routers.kg.run_centrality_analysis",
            return_value={"metric": "betweenness", "nodes": [], "total_nodes": 0},
        ), patch(
            "med_research.web.routers.kg.run_community_detection",
            return_value={
                "communities": [],
                "modularity": 0.0,
                "n_communities": 0,
                "algorithm": "louvain",
            },
        ):
            centrality = client.get("/api/kg/centrality?disease=ra")
            communities = client.get("/api/kg/communities?disease=ra")
        assert centrality.status_code == 200
        assert communities.status_code == 200

    def test_cart_suitability_router(self, client):
        with patch(
            "med_research.web.routers.car_t.run_cart_analysis",
            return_value={
                "genes": [],
                "total_genes": 0,
                "avg_score": 0.0,
                "tier1_count": 0,
                "tier2_count": 0,
                "tier3_count": 0,
                "coverage": {},
                "status": "ready",
            },
        ):
            resp = client.get("/api/cart/suitability?disease=ra")
        assert resp.status_code == 200

    def test_safety_profiles_router(self, client):
        with patch(
            "med_research.web.routers.adverse_events.run_safety_profiling",
            return_value={"profiles": [], "total_drugs": 0, "coverage": {}, "status": "ready"},
        ):
            resp = client.get("/api/safety/profiles?disease=ra")
        assert resp.status_code == 200

    def test_extractor_router(self, client):
        with patch(
            "med_research.web.routers.extractor.run_llm_extraction",
            return_value={
                "query": "lupus",
                "model": "gpt-4o-mini",
                "total_extracted": 0,
                "extractions": [],
                "coverage": {},
                "status": "ready",
            },
        ):
            resp = client.get("/api/llm/extract?q=lupus&disease_id=sle")
        assert resp.status_code == 200


class TestDispatchUnit:
    """Unit tests for pipeline.dispatch helpers and execute_module."""

    def test_standard_to_legacy_zero_total(self):
        from med_research.pipeline.dispatch import standard_to_legacy

        calls: list[tuple[int, str]] = []

        def sink(percent: int, message: str) -> None:
            calls.append((percent, message))

        standard_to_legacy("done", 1, 0, sink)
        assert calls == [(100, "done")]

    def test_progress_reporter_legacy_noop(self):
        from med_research.pipeline.dispatch import ProgressReporter

        reporter = ProgressReporter()
        reporter.legacy()(50, "msg")

    def test_execute_module_unknown_module(self):
        from med_research.pipeline.dispatch import execute_module

        result = execute_module("not_a_real_module_xyz", "sle")
        assert result.success is False
        assert result.errors

    def test_execute_module_blocked_coverage(self):
        from med_research.pipeline.dispatch import execute_module

        with patch(
            "med_research.pipeline.dispatch.get_module",
        ) as mock_get, patch(
            "med_research.pipeline.dispatch.module_coverage",
        ) as mock_cov:
            mock_module = MagicMock()
            mock_module.coverage_inputs.return_value = ("genes",)
            mock_get.return_value = mock_module
            mock_cov.return_value.is_runnable = False
            mock_cov.return_value.limitations = ["blocked"]
            mock_cov.return_value.missing_inputs = []
            mock_cov.return_value.disease_id = "ra"

            result = execute_module("gwas", "ra")
        assert result.success is False

    def test_execute_module_success_with_export(self, tmp_path):
        from med_research.pipeline.dispatch import execute_module

        mock_module = MagicMock()
        mock_module.module_id = "gwas"
        mock_module.coverage_inputs.return_value = ("genes",)
        mock_module.run.return_value = {"hits": []}
        mock_module.build_provenance.return_value = {"module": "gwas"}
        report_path = tmp_path / "report.html"
        mock_module.report.return_value = report_path

        with patch(
            "med_research.pipeline.dispatch.get_module",
            return_value=mock_module,
        ), patch(
            "med_research.pipeline.dispatch.module_coverage",
        ) as mock_cov:
            mock_cov.return_value.is_runnable = True
            result = execute_module("gwas", "ra", export_html=True)
        assert result.success is True
        assert result.report_path == report_path

    def test_execute_module_maps_typed_errors(self):
        from med_research.exceptions import ExternalAPIError
        from med_research.pipeline.dispatch import execute_module

        mock_module = MagicMock()
        mock_module.module_id = "gwas"
        mock_module.coverage_inputs.return_value = ("genes",)
        mock_module.run.side_effect = ExternalAPIError("api down")

        with patch(
            "med_research.pipeline.dispatch.get_module",
            return_value=mock_module,
        ), patch(
            "med_research.pipeline.dispatch.module_coverage",
        ) as mock_cov:
            mock_cov.return_value.is_runnable = True
            result = execute_module("gwas", "ra")
        assert result.success is False
        assert "api down" in result.errors[0]


class TestOfflineAdapterRuns:
    """Exercise registry adapters offline to lift pipeline coverage."""

    @pytest.mark.parametrize(
        "module_id,extra_opts",
        [
            ("knowledge_graph", {}),
            ("drug_repurposing", {}),
            ("network_pharmacology", {"operation": "centrality", "metric": "degree", "top_n": 5}),
            ("gene_expression", {}),
            ("car_t_predictor", {}),
            ("adverse_events", {}),
            ("drug_synergy", {}),
            ("biomarker_discovery", {}),
            ("virtual_screening", {"operation": "untargeted_genes"}),
            ("gwas", {"max_studies": 3}),
            ("enrichment", {}),
            ("ppi", {}),
            ("literature_mining", {"max_per_query": 3}),
            ("clinical_trials", {"max_results": 3}),
            ("cross_disease", {}),
            ("semantic_search", {"query": "lupus", "top": 3}),
        ],
    )
    def test_adapter_run_ra_offline(self, module_id: str, extra_opts: dict):
        adapter = get_module(module_id)
        result = adapter.run("ra", use_cache=True, **extra_opts)
        assert result is not None


class TestExceptionsUnit:
    """Unit tests for exception classification helpers."""

    def test_classify_api_error_json_decode(self):
        import json

        from med_research.exceptions import APIParseError, classify_api_error

        err = classify_api_error(json.JSONDecodeError("bad json", "doc", 0), source="pubmed")
        assert isinstance(err, APIParseError)
        assert "pubmed" in str(err)

    def test_missing_data_error_str(self):
        from med_research.exceptions import MissingDataError

        assert str(MissingDataError("genes.json missing")) == "genes.json missing"
        assert str(MissingDataError()) == "Required data file or field is missing"

    def test_retry_with_backoff_retries_then_succeeds(self):
        from med_research.exceptions import APITimeoutError, retry_with_backoff

        attempts = {"count": 0}

        def flaky():
            attempts["count"] += 1
            if attempts["count"] < 2:
                raise APITimeoutError("temporary")
            return "ok"

        result = retry_with_backoff(flaky, max_attempts=3, source="test")
        assert result == "ok"
        assert attempts["count"] == 2

