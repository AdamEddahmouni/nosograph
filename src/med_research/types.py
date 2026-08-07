"""TypedDict classes for common data shapes in the medical research pipeline.

These reflect the actual data shapes from the Pydantic schemas in
diseases/schemas.py, providing accurate type hints for dict-based APIs without
requiring Pydantic validation at every call site.
"""

from __future__ import annotations

from typing import Any, TypedDict

# ── Core KG entity shapes (mirror diseases/schemas.py Pydantic models) ──


class GeneDict(TypedDict, total=False):
    """Dict shape for gene.json entries — mirrors diseases.schemas.Gene."""

    id: str
    name: str
    chromosome: str
    function: str
    lupus_evidence: str
    odds_ratio: float | None
    references: list[str]
    category: str
    sle_evidence: str
    disease_evidence: str


class DrugDict(TypedDict, total=False):
    """Dict shape for drugs.json entries — mirrors diseases.schemas.Drug."""

    id: str
    name: str
    type: str
    target: str
    mechanism: str
    approval: str
    route: str
    efficacy: str
    references: list[str]
    category: str
    disease_evidence: str
    adverse_effects: str


class PathwayDict(TypedDict, total=False):
    """Dict shape for pathways.json entries — mirrors diseases.schemas.Pathway."""

    id: str
    name: str
    description: str
    key_components: list[str]
    therapeutic_targets: list[str]
    references: list[str]


# ── Drug repurposing candidate shape ──


class CandidateDict(TypedDict, total=False):
    """Dict shape for a scored repurposing candidate (engine.score_candidates)."""

    gene_id: str
    drug_name: str
    drug_id: str
    target_similarity_score: float
    pathway_proximity_score: float
    mechanistic_rationale_score: float
    clinical_evidence_score: float
    adverse_event_score: float
    safety_score: float
    novelty_score: int
    evidence_level: str
    mechanism: str
    rationale: str
    status: str
    kg_pathway_proximity: float
    final_proximity: float
    composite_score: float
    tier: str
    gene_name: str
    gene_category: str
    gene_function: str
    gene_lupus_evidence: str
    gene_odds_ratio: float | None


# ── Pipeline result envelope ──


class PipelineResult(TypedDict, total=False):
    """Success/failure envelope used by web service entry points."""

    success: bool
    data: dict[str, Any]
    errors: list[str]


class KGEntityIndex(TypedDict, total=False):
    """Index of KG entities keyed by entity ID."""

    genes: dict[str, GeneDict]
    drugs: dict[str, DrugDict]
    pathways: dict[str, PathwayDict]
