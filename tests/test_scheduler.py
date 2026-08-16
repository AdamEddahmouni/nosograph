"""Tests for the parallel run-all DAG scheduler."""

from __future__ import annotations

import pytest

from med_research.pipeline.registry import get_module, list_modules
from med_research.pipeline.scheduler import (
    resolve_depends_on,
    run_levels,
    topological_levels,
    validate_dag,
)

pytestmark = pytest.mark.unit


class TestResolveDependsOn:
    def test_knowledge_graph_has_no_dependencies(self):
        assert resolve_depends_on("knowledge_graph") == ()
        assert get_module("knowledge_graph").depends_on == ()

    def test_cross_disease_has_no_dependencies(self):
        assert resolve_depends_on("cross_disease") == ()
        assert get_module("cross_disease").depends_on == ()

    def test_ppi_depends_on_kg_and_repurpose(self):
        assert resolve_depends_on("ppi") == ("knowledge_graph", "drug_repurposing")
        assert get_module("ppi").depends_on == ("knowledge_graph", "drug_repurposing")

    def test_literature_depends_on_knowledge_graph(self):
        assert resolve_depends_on("literature_mining") == ("knowledge_graph",)

    def test_evidence_workspace_depends_on_knowledge_graph(self):
        assert resolve_depends_on("evidence_workspace") == ("knowledge_graph",)

    def test_drug_repurposing_depends_on_knowledge_graph(self):
        assert resolve_depends_on("drug_repurposing") == ("knowledge_graph",)

    def test_biomarker_depends_on_upstream_scoring_modules(self):
        assert resolve_depends_on("biomarker_discovery") == (
            "knowledge_graph",
            "gene_expression",
            "car_t_predictor",
            "drug_repurposing",
            "adverse_events",
            "drug_synergy",
        )

    def test_resolve_depends_on_matches_adapter_metadata(self):
        for module_id in list_modules():
            assert resolve_depends_on(module_id) == get_module(module_id).depends_on


class TestTopologicalLevels:
    def test_kg_is_first_level(self):
        modules = [
            "literature_mining",
            "knowledge_graph",
            "drug_repurposing",
            "clinical_trials",
        ]
        levels = topological_levels(modules)
        assert levels[0] == ["knowledge_graph"]

    def test_independent_modules_share_second_level(self):
        modules = [
            "knowledge_graph",
            "drug_repurposing",
            "literature_mining",
            "clinical_trials",
            "gwas",
        ]
        levels = topological_levels(modules)
        assert levels[0] == ["knowledge_graph"]
        assert set(levels[1]) == {
            "drug_repurposing",
            "literature_mining",
            "clinical_trials",
            "gwas",
        }

    def test_ppi_runs_after_repurpose(self):
        modules = ["knowledge_graph", "drug_repurposing", "ppi"]
        levels = topological_levels(modules)
        assert levels[0] == ["knowledge_graph"]
        assert levels[1] == ["drug_repurposing"]
        assert levels[2] == ["ppi"]

    def test_biomarker_runs_after_upstream_scoring_modules(self):
        module_ids = [
            "knowledge_graph",
            "gene_expression",
            "car_t_predictor",
            "drug_repurposing",
            "adverse_events",
            "drug_synergy",
            "biomarker_discovery",
        ]
        levels = topological_levels(module_ids)
        assert levels[0] == ["knowledge_graph"]
        upstream = {
            "gene_expression",
            "car_t_predictor",
            "drug_repurposing",
            "adverse_events",
            "drug_synergy",
        }
        assert set(levels[1]) == upstream
        assert levels[2] == ["biomarker_discovery"]

    def test_evidence_workspace_runs_after_knowledge_graph(self):
        modules = ["evidence_workspace", "knowledge_graph", "semantic_search"]
        levels = topological_levels(modules)
        assert levels[0] == ["knowledge_graph"]
        assert set(levels[1]) == {"evidence_workspace", "semantic_search"}

    def test_cross_disease_has_no_upstream_dependencies(self):
        modules = ["cross_disease", "knowledge_graph", "literature_mining"]
        levels = topological_levels(modules)
        assert set(levels[0]) == {"cross_disease", "knowledge_graph"}

    def test_cycle_raises(self, monkeypatch):
        import med_research.pipeline.scheduler as sched

        monkeypatch.setattr(
            sched,
            "resolve_depends_on",
            lambda module_id: ("b",) if module_id == "a" else ("a",) if module_id == "b" else (),
        )
        with pytest.raises(ValueError, match="Cycle or unresolved dependencies"):
            topological_levels(["a", "b"])

    def test_validate_dag_rejects_unknown_module(self):
        with pytest.raises(KeyError, match="Unknown pipeline module"):
            validate_dag(["not_a_real_module"])


class TestRunLevels:
    def test_sequential_runner_invokes_each_module(self):
        calls: list[str] = []
        levels = [["knowledge_graph"], ["literature_mining", "clinical_trials"]]
        errors = run_levels(levels, calls.append, parallel=False)
        assert errors == 0
        assert calls == ["knowledge_graph", "literature_mining", "clinical_trials"]

    def test_parallel_runner_invokes_all_modules_in_level(self):
        calls: list[str] = []
        levels = [["knowledge_graph"], ["gwas", "enrichment", "ppi"]]

        def runner(module_id: str) -> None:
            calls.append(module_id)

        errors = run_levels(levels, runner, parallel=True)
        assert errors == 0
        assert calls[0] == "knowledge_graph"
        assert set(calls[1:]) == {"gwas", "enrichment", "ppi"}

    def test_run_levels_counts_errors(self):
        def runner(module_id: str) -> None:
            if module_id == "bad":
                raise RuntimeError("boom")

        errors = run_levels([["good", "bad"]], runner, parallel=False)
        assert errors == 1

    def test_parallel_level_continues_after_failure(self):
        def runner(module_id: str) -> None:
            if module_id == "bad":
                raise RuntimeError("boom")

        errors = run_levels([["good", "bad"]], runner, parallel=True)
        assert errors == 1
