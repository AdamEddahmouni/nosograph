"""Versioned condition similarity algorithm."""

from __future__ import annotations

from uuid import UUID

import networkx as nx

from med_research.biomed.comparison.hpo import HpoContext, _ancestor_closure
from med_research.biomed.comparison.models import (
    ComparisonComponents,
    ComparisonCoverage,
    ComparisonResult,
    ConditionFingerprint,
    SimilarityConfig,
)

_RESEARCH_DISCLAIMER = (
    "For research and exploratory analysis only. Results summarize supporting evidence "
    "and contradictory evidence from imported biomedical sources. Not for clinical "
    "decision-making, treatment recommendations, or probability-of-disease claims."
)

_PLACEHOLDER_RUN_ID = UUID(int=0)
_SCORING_DIMENSIONS = ("phenotype", "gene", "pathway", "intervention")
_MIN_COMPARABLE_DIMENSIONS = 1


def compare_fingerprints(
    left: ConditionFingerprint,
    right: ConditionFingerprint,
    config: SimilarityConfig,
    hpo_context: HpoContext,
) -> ComparisonResult:
    comparable = _comparable_dimensions(left, right)
    missing = [dimension for dimension in _SCORING_DIMENSIONS if dimension not in comparable]

    coverage = ComparisonCoverage(
        left=left.coverage,
        right=right.coverage,
        comparable_dimensions=comparable,
        missing_dimensions=missing,
    )

    if len(comparable) < _MIN_COMPARABLE_DIMENSIONS:
        return ComparisonResult(
            run_id=_PLACEHOLDER_RUN_ID,
            status="insufficient_data",
            left_curie=left.condition_curie,
            right_curie=right.condition_curie,
            overall_score=None,
            coverage=coverage,
            claim_set_fingerprint=_combined_claim_fingerprint(left, right),
            algorithm_id=config.algorithm_id,
            algorithm_version=config.algorithm_version,
            disclaimer=_RESEARCH_DISCLAIMER,
        )

    components = ComparisonComponents()
    component_scores: dict[str, float] = {}
    shared_entities: dict[str, list[str]] = {}
    distinguishing_entities: dict[str, dict[str, list[str]]] = {}

    if "phenotype" in comparable:
        phenotype_score, negative_score = _phenotype_similarity(left, right, hpo_context)
        components = components.model_copy(
            update={"phenotype": phenotype_score, "negative_phenotype": negative_score}
        )
        component_scores["phenotype"] = phenotype_score
        shared_entities["phenotype"] = sorted(
            set(left.positive_phenotypes) & set(right.positive_phenotypes)
        )
        distinguishing_entities["phenotype"] = {
            "left_only": sorted(set(left.positive_phenotypes) - set(right.positive_phenotypes)),
            "right_only": sorted(set(right.positive_phenotypes) - set(left.positive_phenotypes)),
        }

    for dimension, left_values, right_values in (
        ("gene", left.genes, right.genes),
        ("pathway", left.pathways, right.pathways),
        ("intervention", left.interventions, right.interventions),
    ):
        if dimension not in comparable:
            continue
        score = _jaccard(left_values, right_values)
        component_scores[dimension] = score
        shared_entities[dimension] = sorted(set(left_values) & set(right_values))
        distinguishing_entities[dimension] = {
            "left_only": sorted(set(left_values) - set(right_values)),
            "right_only": sorted(set(right_values) - set(left_values)),
        }

    biomarker_shared = sorted(set(left.biomarkers) & set(right.biomarkers))
    if left.biomarkers or right.biomarkers:
        shared_entities["biomarker"] = biomarker_shared
        distinguishing_entities["biomarker"] = {
            "left_only": sorted(set(left.biomarkers) - set(right.biomarkers)),
            "right_only": sorted(set(right.biomarkers) - set(left.biomarkers)),
        }

    effective_weights = _effective_weights(config, comparable)
    overall = sum(
        component_scores[dimension] * effective_weights[dimension] for dimension in comparable
    )

    return ComparisonResult(
        run_id=_PLACEHOLDER_RUN_ID,
        status="comparable",
        left_curie=left.condition_curie,
        right_curie=right.condition_curie,
        overall_score=overall,
        components=components,
        effective_weights=effective_weights,
        shared_entities=shared_entities,
        distinguishing_entities=distinguishing_entities,
        coverage=coverage,
        claim_set_fingerprint=_combined_claim_fingerprint(left, right),
        algorithm_id=config.algorithm_id,
        algorithm_version=config.algorithm_version,
        disclaimer=_RESEARCH_DISCLAIMER,
    )


def _comparable_dimensions(left: ConditionFingerprint, right: ConditionFingerprint) -> list[str]:
    comparable: list[str] = []
    for dimension in _SCORING_DIMENSIONS:
        left_present = left.coverage[dimension].present
        right_present = right.coverage[dimension].present
        if left_present and right_present:
            comparable.append(dimension)
    return comparable


def _effective_weights(config: SimilarityConfig, comparable: list[str]) -> dict[str, float]:
    base = config.base_weights()
    selected = {dimension: base[dimension] for dimension in comparable}
    total = sum(selected.values())
    if total <= 0:
        even = 1.0 / len(comparable)
        return {dimension: even for dimension in comparable}
    return {dimension: weight / total for dimension, weight in selected.items()}


def _jaccard(left_values: list[str], right_values: list[str]) -> float:
    left_set = set(left_values)
    right_set = set(right_values)
    if not left_set and not right_set:
        return 0.0
    union = left_set | right_set
    if not union:
        return 0.0
    return len(left_set & right_set) / len(union)


def _phenotype_similarity(
    left: ConditionFingerprint,
    right: ConditionFingerprint,
    hpo_context: HpoContext,
) -> tuple[float, float]:
    positive = _best_match_average(
        left.positive_phenotypes,
        right.positive_phenotypes,
        hpo_context.graph,
        hpo_context.information_content,
    )
    negative = _best_match_average(
        left.negative_phenotypes,
        right.negative_phenotypes,
        hpo_context.graph,
        hpo_context.information_content,
    )
    return positive, negative


def _best_match_average(
    left_terms: list[str],
    right_terms: list[str],
    graph: nx.DiGraph,
    ic_map: dict[str, float],
) -> float:
    if not left_terms or not right_terms:
        return 0.0
    left_to_right = [
        max(_term_similarity(left, right, graph, ic_map) for right in right_terms)
        for left in left_terms
    ]
    right_to_left = [
        max(_term_similarity(right, left, graph, ic_map) for left in left_terms)
        for right in right_terms
    ]
    return sum(left_to_right + right_to_left) / (len(left_to_right) + len(right_to_left))


def _term_similarity(
    left_term: str,
    right_term: str,
    graph: nx.DiGraph,
    ic_map: dict[str, float],
) -> float:
    if left_term == right_term:
        return 1.0
    left_closure = _ancestor_closure(graph, left_term)
    right_closure = _ancestor_closure(graph, right_term)
    intersection = left_closure & right_closure
    union = left_closure | right_closure
    jaccard = len(intersection) / len(union) if union else 0.0
    if not intersection:
        return jaccard
    ic_values = [ic_map.get(term, 0.0) for term in intersection]
    ic_max = max(ic_values) if ic_values else 0.0
    ic_norm = ic_max / max(ic_map.values()) if ic_map else 0.0
    return (0.7 * jaccard) + (0.3 * ic_norm)


def _combined_claim_fingerprint(left: ConditionFingerprint, right: ConditionFingerprint) -> str:
    from med_research.biomed.identifiers import fingerprint_json

    return fingerprint_json(
        {
            "left": left.claim_set_fingerprint,
            "right": right.claim_set_fingerprint,
        }
    )
