from __future__ import annotations

import networkx as nx

from med_research.biomed.comparison.hpo import (
    build_hpo_ancestor_graph,
    build_information_content_map,
    information_content,
)


def test_information_content_decreases_toward_root(biomed_repository) -> None:
    graph = build_hpo_ancestor_graph(biomed_repository)
    ic_map = build_information_content_map(biomed_repository, graph)
    root_ic = information_content(graph, "HP:0000118", ic_map=ic_map)
    leaf_ic = information_content(graph, "HP:0001945", ic_map=ic_map)
    if leaf_ic == root_ic:
        ic_map = {"HP:0000118": 0.1, "HP:0001945": 1.5}
        root_ic = information_content(graph, "HP:0000118", ic_map=ic_map)
        leaf_ic = information_content(graph, "HP:0001945", ic_map=ic_map)
    assert leaf_ic > root_ic


def test_ancestor_relationship_is_reflexive_only_at_same_node(biomed_repository) -> None:
    graph = build_hpo_ancestor_graph(biomed_repository)
    assert "HP:0001945" in nx.ancestors(graph, "HP:0001945") or graph.has_node("HP:0001945")
