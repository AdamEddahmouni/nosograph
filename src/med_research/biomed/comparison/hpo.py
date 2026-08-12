"""HPO ancestor graph and information-content helpers."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from uuid import UUID

import networkx as nx

from med_research.biomed.models import Predicate
from med_research.biomed.repository import BiomedicalRepository

_HPO_RESOURCE = "hp"
_HPOA_RESOURCE = "hpoa"
_GRAPH_CACHE: dict[tuple[str, str], nx.DiGraph] = {}


@dataclass(frozen=True)
class HpoContext:
    graph: nx.DiGraph
    information_content: dict[str, float]
    hp_snapshot_id: UUID | None
    hpoa_snapshot_id: UUID | None


def build_hpo_context(repository: BiomedicalRepository) -> HpoContext:
    graph = build_hpo_ancestor_graph(repository)
    ic_map = build_information_content_map(repository, graph)
    hp_snapshot = repository.get_active_snapshot(_HPO_RESOURCE)
    hpoa_snapshot = repository.get_active_snapshot(_HPOA_RESOURCE)
    return HpoContext(
        graph=graph,
        information_content=ic_map,
        hp_snapshot_id=hp_snapshot.id if hp_snapshot else None,
        hpoa_snapshot_id=hpoa_snapshot.id if hpoa_snapshot else None,
    )


def build_hpo_ancestor_graph(repository: BiomedicalRepository) -> nx.DiGraph:
    hp_snapshot = repository.get_active_snapshot(_HPO_RESOURCE)
    if hp_snapshot is None:
        return nx.DiGraph()
    cache_key = (str(repository.database.path), str(hp_snapshot.id))
    cached = _GRAPH_CACHE.get(cache_key)
    if cached is not None:
        return cached
    graph = _load_hpo_ancestor_graph(repository, hp_snapshot.id)
    _GRAPH_CACHE[cache_key] = graph
    return graph


def _load_hpo_ancestor_graph(repository: BiomedicalRepository, snapshot_id: UUID) -> nx.DiGraph:
    graph: nx.DiGraph = nx.DiGraph()
    with repository.database.connect() as connection:
        rows = connection.execute(
            """
            SELECT c.subject_curie, c.object_curie
            FROM claims c
            JOIN entities e ON e.primary_curie = c.subject_curie
            WHERE c.predicate = ?
              AND c.subject_curie LIKE 'HP:%'
              AND c.object_curie LIKE 'HP:%'
              AND e.created_in_snapshot_id = ?
            """,
            (Predicate.IS_A.value, str(snapshot_id)),
        ).fetchall()

    for row in rows:
        graph.add_edge(row["subject_curie"], row["object_curie"])
    return graph


def build_information_content_map(
    repository: BiomedicalRepository,
    graph: nx.DiGraph,
) -> dict[str, float]:
    hpoa_snapshot = repository.get_active_snapshot(_HPOA_RESOURCE)
    if hpoa_snapshot is None:
        return {}

    condition_terms: dict[str, set[str]] = {}
    with repository.database.connect() as connection:
        rows = connection.execute(
            """
            SELECT c.subject_curie, c.object_curie, c.qualifiers_json
            FROM claims c
            JOIN claim_evidence e ON e.claim_id = c.id
            WHERE c.predicate = ?
              AND e.snapshot_id = ?
            """,
            (Predicate.HAS_PHENOTYPE.value, str(hpoa_snapshot.id)),
        ).fetchall()

    for row in rows:
        qualifiers = _json_loads(row["qualifiers_json"])
        if qualifiers.get("negated"):
            continue
        condition_terms.setdefault(row["subject_curie"], set()).add(row["object_curie"])

    if not condition_terms:
        return {}

    total_conditions = len(condition_terms)
    term_counts: dict[str, int] = {}
    for terms in condition_terms.values():
        expanded: set[str] = set()
        for term in terms:
            expanded.update(_ancestor_closure(graph, term))
        for term in expanded:
            term_counts[term] = term_counts.get(term, 0) + 1

    ic_map: dict[str, float] = {}
    for term, count in term_counts.items():
        ic_map[term] = -math.log(count / total_conditions)
    return ic_map


def information_content(
    graph: nx.DiGraph,
    term: str,
    *,
    ic_map: dict[str, float] | None = None,
) -> float:
    if ic_map is not None and term in ic_map:
        return ic_map[term]
    if graph.has_node(term):
        return 0.0
    return 0.0


def _ancestor_closure(graph: nx.DiGraph, term: str) -> set[str]:
    if not graph.has_node(term):
        return {term}
    return set(nx.ancestors(graph, term)) | {term}


def _json_loads(value: str | None) -> dict[str, object]:
    if not value:
        return {}
    loaded = json.loads(value)
    if isinstance(loaded, dict):
        return loaded
    return {}
