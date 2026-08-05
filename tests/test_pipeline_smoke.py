import pytest

pytestmark = pytest.mark.integration


class TestPipelineSmoke:
    """End-to-end smoke tests for the SLE pipeline."""

    def test_build_graph_and_score_candidates(self):
        from med_research.pipeline.knowledge_graph.builder import build_graph
        from med_research.pipeline.knowledge_graph.config import load_genes
        from med_research.pipeline.drug_repurposing.engine import (
            identify_untargeted_genes,
            score_candidates,
        )

        graph = build_graph("sle")
        assert graph.number_of_nodes() >= 40
        assert graph.number_of_edges() >= 50

        genes = load_genes("sle")
        genes_index = {g["id"]: g for g in genes["genes"]}

        import json
        from pathlib import Path

        dr_data_dir = (
            Path(__file__).parent.parent
            / "src" / "med_research" / "pipeline" / "drug_repurposing" / "data"
        )
        candidates_data = json.loads(
            (dr_data_dir / "candidates.json").read_text(encoding="utf-8")
        )
        candidates = candidates_data["repurposing_candidates"]

        untargeted = identify_untargeted_genes(graph)
        untargeted_ids = {g["id"] for g in untargeted}

        scored = score_candidates(graph, candidates, genes_index)
        scored = [c for c in scored if c["gene_id"] in untargeted_ids]

        assert len(scored) > 0
        for c in scored:
            assert "composite_score" in c
            assert isinstance(c["composite_score"], float)
            assert 0.0 <= c["composite_score"] <= 10.0
            assert "tier" in c

        scores = [c["composite_score"] for c in scored]
        assert max(scores) > 0.0
        assert all(s >= 0.0 for s in scores)
