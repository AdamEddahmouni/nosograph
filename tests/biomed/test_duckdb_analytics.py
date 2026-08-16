"""Unit tests for DuckDBBiomedicalEngine."""

from __future__ import annotations

from typing import Any

from med_research.biomed.analytics.duckdb_engine import DuckDBBiomedicalEngine
from med_research.biomed.identifiers import (
    claim_evidence_uuid,
    claim_uuid,
    entity_revision_uuid,
    entity_uuid,
)
from med_research.biomed.models import (
    Claim,
    ClaimEvidence,
    Entity,
    EntityRevision,
    EntityType,
    EvidenceDirection,
    Predicate,
)
from med_research.biomed.repository import BiomedicalRepository


def test_duckdb_analytics_engine(repository: BiomedicalRepository, mondo_snapshot: Any) -> None:
    repository.upsert_snapshot(mondo_snapshot)

    # Add entities
    d_ent_id = entity_uuid(EntityType.CONDITION, "MONDO:0007915")
    d_ent = Entity(
        id=d_ent_id,
        primary_curie="MONDO:0007915",
        entity_type=EntityType.CONDITION,
        canonical_name="Systemic Lupus Erythematosus",
        created_in_snapshot_id=mondo_snapshot.id,
    )
    repository.upsert_entity(d_ent)
    repository.add_entity_revision(
        EntityRevision(
            id=entity_revision_uuid(d_ent_id, mondo_snapshot.id),
            entity_id=d_ent_id,
            snapshot_id=mondo_snapshot.id,
            label="Systemic Lupus Erythematosus",
        )
    )

    g_ent_id = entity_uuid(EntityType.GENE, "HGNC:TNF")
    g_ent = Entity(
        id=g_ent_id,
        primary_curie="HGNC:TNF",
        entity_type=EntityType.GENE,
        canonical_name="TNF",
        created_in_snapshot_id=mondo_snapshot.id,
    )
    repository.upsert_entity(g_ent)
    repository.add_entity_revision(
        EntityRevision(
            id=entity_revision_uuid(g_ent_id, mondo_snapshot.id),
            entity_id=g_ent_id,
            snapshot_id=mondo_snapshot.id,
            label="TNF",
        )
    )

    # Add claim & evidence
    c_id = claim_uuid("MONDO:0007915", Predicate.ASSOCIATED_WITH_GENE, "HGNC:TNF")
    claim = Claim(
        id=c_id,
        subject_curie="MONDO:0007915",
        predicate=Predicate.ASSOCIATED_WITH_GENE,
        object_curie="HGNC:TNF",
    )
    repository.add_claim(claim)

    ev_id = claim_evidence_uuid(c_id, mondo_snapshot.id, EvidenceDirection.SUPPORTING, "REC_TNF")
    evidence = ClaimEvidence(
        id=ev_id,
        claim_id=c_id,
        snapshot_id=mondo_snapshot.id,
        direction=EvidenceDirection.SUPPORTING,
        source_record_id="REC_TNF",
        confidence_score=0.95,
    )
    repository.add_claim_evidence(evidence)

    # Initialize DuckDB Engine
    engine = DuckDBBiomedicalEngine(repository.database.path)
    stats = engine.get_summary_statistics()

    assert stats["total_entities"] >= 2
    assert stats["total_claims"] >= 1
    assert stats["total_evidence"] >= 1
    assert "gene" in stats["entity_type_distribution"]

    # Target prioritization
    targets = engine.prioritize_targets_vectorized("MONDO:0007915", top_k=5)
    assert len(targets) >= 1
    top = targets[0]
    assert top.target_curie == "HGNC:TNF"
    assert top.supporting_count == 1
    assert top.contradictory_count == 0
    assert top.evidence_score > 0.0

    # Subgraph
    subgraph = engine.find_multi_hop_subgraph("MONDO:0007915", max_hops=2)
    assert len(subgraph) >= 1
    assert subgraph[0].target == "HGNC:TNF"

    # Cross-Disease Matrix
    matrix_res = engine.compute_cross_disease_matrix(["MONDO:0007915", "MONDO:0008383"])
    assert len(matrix_res["conditions"]) == 2
    assert len(matrix_res["matrix"]) == 2
    assert matrix_res["matrix"][0][0] == 1.0
    assert matrix_res["matrix"][1][1] == 1.0
    assert "MONDO:0007915___MONDO:0008383" in matrix_res["details"]

    # Druggability Distribution
    drug_dist = engine.get_druggability_distribution("MONDO:0007915")
    assert "distribution" in drug_dist
    assert drug_dist["disease_curie"] == "MONDO:0007915"

