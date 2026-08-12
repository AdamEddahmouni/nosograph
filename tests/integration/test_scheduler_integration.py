"""Scheduler integration tests with ``execute_module`` dispatch."""

from __future__ import annotations

import pytest

from med_research.pipeline.dispatch import execute_module
from med_research.pipeline.scheduler import resolve_depends_on, run_levels, validate_dag

DISEASE = "ra"

pytestmark = [pytest.mark.integration]




class TestSchedulerRegistryIntegration:
    """Real multi-level DAG execution using registry adapters."""

    def test_ppi_level_runs_after_kg_and_repurpose(self, offline_pipeline_http_mocks):
        module_ids = ["knowledge_graph", "drug_repurposing", "ppi"]
        levels = validate_dag(module_ids)
        assert levels[0] == ["knowledge_graph"]
        assert levels[1] == ["drug_repurposing"]
        assert levels[2] == ["ppi"]

        executed: list[str] = []

        def runner(module_id: str) -> None:
            result = execute_module(module_id, DISEASE, use_cache=True)
            assert result.success, f"{module_id} failed: {result.errors}"
            executed.append(module_id)

        errors = 0
        for level in levels:
            errors += run_levels([level], runner, parallel=False)

        assert errors == 0
        assert executed == module_ids

    def test_parallel_level_invokes_independent_modules(self, offline_pipeline_http_mocks):
        module_ids = [
            "knowledge_graph",
            "drug_repurposing",
            "gwas",
            "enrichment",
            "literature_mining",
        ]
        levels = validate_dag(module_ids)
        executed: list[str] = []

        def runner(module_id: str) -> None:
            result = execute_module(module_id, DISEASE, use_cache=True)
            assert result.success, f"{module_id} failed: {result.errors}"
            executed.append(module_id)

        errors = run_levels(levels, runner, parallel=True)

        assert errors == 0
        assert executed[0] == "knowledge_graph"
        assert set(executed[1:]) == {
            "drug_repurposing",
            "gwas",
            "enrichment",
            "literature_mining",
        }

    def test_biomarker_level_runs_after_upstream_modules(self):
        module_ids = [
            "knowledge_graph",
            "gene_expression",
            "car_t_predictor",
            "drug_repurposing",
            "adverse_events",
            "drug_synergy",
            "biomarker_discovery",
        ]
        levels = validate_dag(module_ids)
        assert levels[0] == ["knowledge_graph"]
        assert set(levels[1]) == {
            "gene_expression",
            "car_t_predictor",
            "drug_repurposing",
            "adverse_events",
            "drug_synergy",
        }
        assert levels[2] == ["biomarker_discovery"]

    def test_evidence_and_semantic_modules_follow_knowledge_graph(self):
        module_ids = [
            "knowledge_graph",
            "evidence_gather",
            "semantic_search",
            "llm_extractor",
            "evidence_monitor",
            "evidence_workspace",
        ]
        levels = validate_dag(module_ids)
        assert levels[0] == ["knowledge_graph"]
        assert set(levels[1]) == {
            "evidence_gather",
            "semantic_search",
            "llm_extractor",
            "evidence_monitor",
            "evidence_workspace",
        }
        for module_id in module_ids[1:]:
            assert resolve_depends_on(module_id) == ("knowledge_graph",)

    def test_evidence_semantic_level_executes_after_kg(
        self,
        offline_pipeline_http_mocks,
        evidence_api_mocks,
    ):
        module_ids = ["knowledge_graph", "evidence_gather", "semantic_search"]
        levels = validate_dag(module_ids)
        executed: list[str] = []

        def runner(module_id: str) -> None:
            result = execute_module(module_id, DISEASE, use_cache=True)
            if module_id == "semantic_search" and not result.success:
                pytest.skip(f"semantic_search unavailable offline: {result.errors}")
            assert result.success, f"{module_id} failed: {result.errors}"
            executed.append(module_id)

        errors = 0
        for level in levels:
            errors += run_levels([level], runner, parallel=False)

        assert errors == 0
        assert executed == module_ids

    def test_biomarker_depends_on_upstream_producers(self):
        """Biomarker waits for all upstream module outputs before running."""
        expected = (
            "knowledge_graph",
            "gene_expression",
            "car_t_predictor",
            "drug_repurposing",
            "adverse_events",
            "drug_synergy",
        )
        assert resolve_depends_on("biomarker_discovery") == expected
        module_ids = list(expected) + ["biomarker_discovery"]
        levels = validate_dag(module_ids)
        assert levels[-1] == ["biomarker_discovery"]

    def test_resolve_depends_on_matches_registry_metadata(self):
        assert resolve_depends_on("knowledge_graph") == ()
        assert resolve_depends_on("ppi") == ("knowledge_graph", "drug_repurposing")
        assert "knowledge_graph" in resolve_depends_on("literature_mining")
        assert resolve_depends_on("evidence_gather") == ("knowledge_graph",)
        assert resolve_depends_on("semantic_search") == ("knowledge_graph",)
        assert resolve_depends_on("biomarker_discovery") == (
            "knowledge_graph",
            "gene_expression",
            "car_t_predictor",
            "drug_repurposing",
            "adverse_events",
            "drug_synergy",
        )
