"""Tests for BiomedicalGraphAnalytics pathfinding and target prioritization."""

from __future__ import annotations

from typing import Any

from med_research.biomed.graph_analytics import BiomedicalGraphAnalytics
from med_research.biomed.identifiers import claim_evidence_uuid, claim_uuid
from med_research.biomed.models import Claim, ClaimEvidence, EvidenceDirection, Predicate
from med_research.biomed.repository import BiomedicalRepository


def test_graph_analytics_pathfinding(repository: BiomedicalRepository) -> None:
    analytics = BiomedicalGraphAnalytics(repository)
    paths = analytics.find_shortest_paths("MONDO:0007915", "MONDO:0007915", max_depth=3)
    assert len(paths) == 1
    assert paths[0].nodes == ["MONDO:0007915"]
    assert paths[0].score == 1.0


def test_graph_analytics_prioritize_targets(repository: BiomedicalRepository, mondo_snapshot: Any) -> None:
    repository.upsert_snapshot(mondo_snapshot)
    c_id = claim_uuid("MONDO:0007915", Predicate.TREATED_BY, "UNIPROT:P01375")
    claim = Claim(
        id=c_id,
        subject_curie="MONDO:0007915",
        object_curie="UNIPROT:P01375",
        predicate=Predicate.TREATED_BY,
    )
    repository.add_claim(claim)

    ev_id = claim_evidence_uuid(c_id, mondo_snapshot.id, EvidenceDirection.SUPPORTING, "REC001")
    evidence = ClaimEvidence(
        id=ev_id,
        claim_id=c_id,
        snapshot_id=mondo_snapshot.id,
        direction=EvidenceDirection.SUPPORTING,
        source_record_id="REC001",
        evidence_type="test",
    )
    repository.add_claim_evidence(evidence)

    analytics = BiomedicalGraphAnalytics(repository)
    scores = analytics.prioritize_disease_targets("MONDO:0007915", top_k=5)
    assert len(scores) >= 1
    top = scores[0]
    assert top.target_curie == "UNIPROT:P01375"
    assert top.supporting_evidence_count >= 1
    assert top.combined_vulnerability_score > 0.0

