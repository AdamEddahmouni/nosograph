from __future__ import annotations

from uuid import uuid4

import networkx as nx
import pytest

from med_research.biomed.comparison.algorithm import compare_fingerprints
from med_research.biomed.comparison.hpo import HpoContext
from med_research.biomed.comparison.models import (
    ConditionFingerprint,
    DimensionCoverage,
    SimilarityConfig,
)


def sample_fingerprint() -> ConditionFingerprint:
    coverage = {
        dimension: DimensionCoverage(
            present=dimension in {"phenotype", "gene"},
            count=1 if dimension in {"phenotype", "gene"} else 0,
        )
        for dimension in ("phenotype", "gene", "pathway", "intervention", "biomarker")
    }
    return ConditionFingerprint(
        condition_curie="MONDO:0000001",
        positive_phenotypes=["HP:0001945"],
        genes=["HGNC:1100"],
        coverage=coverage,
        claim_set_fingerprint="fp-sample",
    )


def fingerprint_with_phenotypes(terms: list[str]) -> ConditionFingerprint:
    coverage = {
        dimension: DimensionCoverage(
            present=dimension == "phenotype", count=1 if dimension == "phenotype" else 0
        )
        for dimension in ("phenotype", "gene", "pathway", "intervention", "biomarker")
    }
    return ConditionFingerprint(
        condition_curie="MONDO:0000001",
        positive_phenotypes=terms,
        coverage=coverage,
        claim_set_fingerprint="fp-phenotype",
    )


def fingerprint_with_genes_only(genes: list[str]) -> ConditionFingerprint:
    coverage = {
        dimension: DimensionCoverage(
            present=dimension == "gene", count=len(genes) if dimension == "gene" else 0
        )
        for dimension in ("phenotype", "gene", "pathway", "intervention", "biomarker")
    }
    return ConditionFingerprint(
        condition_curie="MONDO:0000002",
        genes=genes,
        coverage=coverage,
        claim_set_fingerprint="fp-gene",
    )


def empty_fingerprint() -> ConditionFingerprint:
    coverage = {
        dimension: DimensionCoverage(present=False, count=0)
        for dimension in ("phenotype", "gene", "pathway", "intervention", "biomarker")
    }
    return ConditionFingerprint(
        condition_curie="MONDO:empty",
        coverage=coverage,
        claim_set_fingerprint="fp-empty",
    )


def hpo_context() -> HpoContext:
    graph = nx.DiGraph()
    graph.add_edge("HP:0001945", "HP:0000118")
    graph.add_edge("HP:0001250", "HP:0000118")
    ic_map = {
        "HP:0000118": 0.1,
        "HP:0001945": 1.5,
        "HP:0001250": 1.2,
    }
    return HpoContext(
        graph=graph, information_content=ic_map, hp_snapshot_id=uuid4(), hpoa_snapshot_id=uuid4()
    )


def test_identical_fingerprints_score_maximally() -> None:
    fp = sample_fingerprint()
    result = compare_fingerprints(fp, fp, SimilarityConfig.v1_default(), hpo_context())
    assert result.status == "comparable"
    assert result.overall_score == pytest.approx(1.0)


def test_disjoint_phenotypes_do_not_false_overlap() -> None:
    context = hpo_context()
    context.graph.add_node("HP:0009999")
    left = fingerprint_with_phenotypes(["HP:0009999"])
    right = fingerprint_with_phenotypes(["HP:0001250"])
    result = compare_fingerprints(left, right, SimilarityConfig.v1_default(), context)
    assert result.components.phenotype is not None
    assert result.components.phenotype < 0.2


def test_missing_dimension_renormalizes_weights() -> None:
    left = fingerprint_with_genes_only(["HGNC:1100"])
    right = fingerprint_with_genes_only(["HGNC:1100"])
    result = compare_fingerprints(left, right, SimilarityConfig.v1_default(), hpo_context())
    assert result.effective_weights["gene"] == pytest.approx(1.0)


def test_inadequate_data_returns_insufficient_data() -> None:
    left = empty_fingerprint()
    right = empty_fingerprint()
    result = compare_fingerprints(left, right, SimilarityConfig.v1_default(), hpo_context())
    assert result.status == "insufficient_data"
    assert result.overall_score is None
