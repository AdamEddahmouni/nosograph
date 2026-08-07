"""Tests for disease-aware virtual screening strategies."""

import pytest


DISEASES = ["sle", "ra", "ms", "ss", "ssc", "t1d", "ibd"]


def test_strategy_for_each_disease_is_valid():
    from med_research.pipeline.virtual_screening.screening_strategy import (
        SCORE_DIMENSIONS,
        strategy_for_disease,
    )

    for disease_id in DISEASES:
        strategy = strategy_for_disease(disease_id)
        assert strategy.disease_id == disease_id
        assert strategy.pathway_keywords
        assert strategy.mechanism_keywords
        assert strategy.reference_drug_ids
        assert set(strategy.weights) == set(SCORE_DIMENSIONS)
        assert sum(strategy.weights.values()) == pytest.approx(1.0)
        assert strategy.source
        assert strategy.limitations


def test_unknown_disease_never_uses_sle_strategy():
    from med_research.pipeline.virtual_screening.screening_strategy import strategy_for_disease

    with pytest.raises(ValueError):
        strategy_for_disease("not-a-disease")


def test_strategy_fingerprint_is_deterministic():
    from med_research.pipeline.virtual_screening.screening_strategy import (
        strategy_fingerprint,
        strategy_for_disease,
    )

    strategy = strategy_for_disease("ibd")
    assert strategy_fingerprint(strategy) == strategy_fingerprint(strategy)
    assert len(strategy_fingerprint(strategy)) == 64


def test_composite_score_accepts_strategy_weights():
    from med_research.pipeline.virtual_screening.screening import compute_composite_score

    scores = {dimension: 8.0 for dimension in (
        "binding_estimate",
        "druglikeness",
        "target_complementarity",
        "similarity_score",
        "novelty_score",
    )}
    weights = {
        "binding_estimate": 0.1,
        "druglikeness": 0.1,
        "target_complementarity": 0.5,
        "similarity_score": 0.2,
        "novelty_score": 0.1,
    }
    assert compute_composite_score(scores, weights) == 8.0


def test_target_complementarity_uses_active_disease_vocabulary():
    from med_research.pipeline.virtual_screening.screening import compute_target_complementarity

    gene = {
        "id": "IL23R",
        "category": "IL-23 / Th17 Axis",
        "function": "mucosal cytokine signaling",
    }
    compound = {
        "mechanism": "IL-23 / Th17 inhibitor",
        "target": "IL23R",
        "category": "IBD therapy",
    }
    ibd = compute_target_complementarity(compound, gene, disease_id="ibd")
    sle = compute_target_complementarity(compound, gene, disease_id="sle")
    assert ibd > sle


def test_screening_results_include_strategy_provenance():
    from med_research.pipeline.virtual_screening.screening import screen_compounds

    result = screen_compounds(
        target_genes=[],
        compound_library=[],
        disease_id="ibd",
    )
    assert result["disease_id"] == "ibd"
    assert result["strategy_id"] == "ibd-screening-v1"
    assert len(result["strategy_fingerprint"]) == 64
    assert result["coverage"]["status"] == "ready"
    assert result["strategy_limitations"]


@pytest.mark.parametrize("disease_id", DISEASES)
def test_all_diseases_screen_with_ready_strategy(disease_id):
    from med_research.pipeline.virtual_screening.screening import (
        build_compound_library,
        load_kg_genes,
        screen_compounds,
    )

    genes = load_kg_genes(disease_id)
    target_gene = next(iter(genes))
    result = screen_compounds(
        target_genes=[target_gene],
        compound_library=build_compound_library(disease_id)[:1],
        disease_id=disease_id,
    )
    assert result["status"] == "ready"
    assert result["coverage"]["level"] == "full"
    assert result["disease_id"] == disease_id
    assert result["strategy_id"].startswith(f"{disease_id}-")
    assert result["strategy_fingerprint"]


def test_non_sle_similarity_does_not_use_shared_sle_candidates(monkeypatch):
    from med_research.pipeline.virtual_screening import screening

    def fail_if_read(*args, **kwargs):
        raise AssertionError("shared SLE candidate data was consulted")

    monkeypatch.setattr(screening.Path, "read_text", fail_if_read)
    score = screening.compute_similarity_score(
        {"name": "Any compound", "category": "Unknown"},
        {"id": "IL23R"},
        disease_id="ibd",
    )
    assert score == 3.0


def test_missing_strategy_is_blocked_without_fallback(monkeypatch):
    from med_research.diseases.base import Disease
    from med_research.pipeline.virtual_screening.screening import screen_compounds

    monkeypatch.setattr(Disease, "get_screening_profile", lambda self: {})
    result = screen_compounds(target_genes=[], compound_library=[], disease_id="ra")
    assert result["status"] == "blocked"
    assert result["coverage"]["status"] == "blocked"
    assert result["strategy_id"] == ""
