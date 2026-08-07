"""Knowledge-graph explanations for workspace candidates."""

from __future__ import annotations

import networkx as nx

from .schemas import GraphExplanation, RankedCandidate


def _disease_node(graph: nx.Graph) -> str | None:
    return next(
        (node for node, data in graph.nodes(data=True) if data.get("type") == "disease"), None
    )


def build_graph_explanations(
    candidates: list[RankedCandidate], disease_id: str = "sle", graph: nx.Graph | None = None
) -> list[GraphExplanation]:
    if graph is None:
        from med_research.pipeline.knowledge_graph.builder import build_graph

        graph = build_graph(disease_id)
    disease = _disease_node(graph)
    explanations = []
    for candidate in candidates:
        explanation_id = f"graph:{candidate.candidate_id}"
        if candidate.candidate_id not in graph:
            explanations.append(
                GraphExplanation(
                    explanation_id=explanation_id,
                    candidate_id=candidate.candidate_id,
                    status="no_path_found",
                    reason="Candidate is not present in the disease knowledge graph.",
                )
            )
            continue
        if disease is None:
            explanations.append(
                GraphExplanation(
                    explanation_id=explanation_id,
                    candidate_id=candidate.candidate_id,
                    status="no_path_found",
                    reason="Knowledge graph has no disease node.",
                )
            )
            continue
        try:
            path = nx.shortest_path(graph.to_undirected(), candidate.candidate_id, disease)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            explanations.append(
                GraphExplanation(
                    explanation_id=explanation_id,
                    candidate_id=candidate.candidate_id,
                    status="no_path_found",
                    reason="No connected path to the disease node was found.",
                )
            )
            continue
        relationships = []
        labels = []
        for source, target in zip(path[:-1], path[1:], strict=True):
            data = graph.get_edge_data(source, target) or graph.get_edge_data(target, source) or {}
            if isinstance(data, dict) and "type" not in data:
                data = next(iter(data.values()), {})
            relationships.append(str(data.get("type", "RELATED_TO")))
            labels.append(f"{source} —{relationships[-1]}→ {target}")
        explanations.append(
            GraphExplanation(
                explanation_id=explanation_id,
                candidate_id=candidate.candidate_id,
                status="found",
                path_node_ids=path,
                path_labels=[str(graph.nodes[node].get("label", node)) for node in path],
                relationship_labels=relationships,
                reason="Real path found in the disease knowledge graph.",
            )
        )
    return explanations
