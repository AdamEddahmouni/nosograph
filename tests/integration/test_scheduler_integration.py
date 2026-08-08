"""Scheduler integration tests with ``execute_module`` dispatch."""

from __future__ import annotations

import pytest

from med_research.pipeline.dispatch import execute_module
from med_research.pipeline.scheduler import resolve_depends_on, run_levels, validate_dag

pytestmark = pytest.mark.integration

DISEASE = "ra"


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

    def test_resolve_depends_on_matches_registry_metadata(self):
        assert resolve_depends_on("knowledge_graph") == ()
        assert resolve_depends_on("ppi") == ("knowledge_graph", "drug_repurposing")
        assert "knowledge_graph" in resolve_depends_on("literature_mining")
