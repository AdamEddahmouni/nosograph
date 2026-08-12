"""Bounded NetworkX projection of claim graphs."""

from __future__ import annotations

import networkx as nx

from med_research.biomed.identifiers import normalize_curie
from med_research.biomed.repository import BiomedicalRepository


def project_claim_graph(
    repository: BiomedicalRepository,
    root_curie: str,
    max_hops: int = 2,
    max_nodes: int = 500,
) -> nx.MultiDiGraph:
    if not 0 <= max_hops <= 3:
        raise ValueError("max_hops must be between 0 and 3")
    if not 1 <= max_nodes <= 2000:
        raise ValueError("max_nodes must be between 1 and 2000")
    graph: nx.MultiDiGraph = nx.MultiDiGraph()
    frontier = {normalize_curie(root_curie)}
    visited: set[str] = set()
    for _depth in range(max_hops + 1):
        next_frontier: set[str] = set()
        for curie in sorted(frontier):
            if curie in visited or graph.number_of_nodes() >= max_nodes:
                continue
            visited.add(curie)
            if curie not in graph:
                graph.add_node(curie)
            for claim_view in repository.list_claims(curie):
                object_curie = claim_view.object_curie
                if object_curie not in graph and graph.number_of_nodes() >= max_nodes:
                    continue
                if object_curie not in graph:
                    graph.add_node(object_curie)
                graph.add_edge(
                    curie,
                    object_curie,
                    key=str(claim_view.claim.id),
                    type=claim_view.claim.predicate.value,
                )
                next_frontier.add(object_curie)
        frontier = next_frontier
    return graph
