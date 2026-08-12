import networkx as nx
import pytest

from med_research.pipeline.evidence_workspace.graph import build_graph_explanations
from med_research.pipeline.evidence_workspace.schemas import RankedCandidate

pytestmark = pytest.mark.unit


def candidate(candidate_id):
    return RankedCandidate(
        candidate_id=candidate_id,
        candidate_type="drug",
        name=candidate_id,
        score=50,
        confidence_band="moderate",
        explanation="heuristic",
    )


def test_graph_explanation_reports_real_path_and_missing_candidate():
    graph = nx.MultiDiGraph()
    graph.add_node("SLE", type="disease", label="Systemic Lupus Erythematosus")
    graph.add_node("JAK1", type="gene", label="JAK1")
    graph.add_node("baricitinib", type="drug", label="Baricitinib")
    graph.add_edge("baricitinib", "JAK1", type="TARGETS")
    graph.add_edge("JAK1", "SLE", type="ASSOCIATED_WITH")

    result = build_graph_explanations([candidate("baricitinib"), candidate("unknown")], graph=graph)

    assert result[0].status == "found"
    assert result[0].path_node_ids == ["baricitinib", "JAK1", "SLE"]
    assert result[0].relationship_labels == ["TARGETS", "ASSOCIATED_WITH"]
    assert result[1].status == "no_path_found"
