from __future__ import annotations

from uuid import uuid4

from med_research.biomed.evidence_quality import derive_evidence_quality
from med_research.biomed.models import ClaimEvidence, EvidenceDirection


def test_derive_evidence_quality_defaults_to_unknown() -> None:
    evidence = ClaimEvidence(
        id=uuid4(),
        claim_id=uuid4(),
        snapshot_id=uuid4(),
        direction=EvidenceDirection.SUPPORTING,
        source_record_id="HP:000001",
    )
    quality = derive_evidence_quality(evidence)
    assert quality.species_context == "unknown"
    assert quality.study_design == "unknown"
    assert quality.origin_class == "UNKNOWN_ORIGIN_CLASS"


def test_derive_evidence_quality_detects_human_and_curator() -> None:
    evidence = ClaimEvidence(
        id=uuid4(),
        claim_id=uuid4(),
        snapshot_id=uuid4(),
        direction=EvidenceDirection.SUPPORTING,
        source_record_id="PMID:123",
        population="human cohort",
        curator="expert-curator",
        extraction_method="hpoa_import",
        sample_size=120,
    )
    quality = derive_evidence_quality(evidence)
    assert quality.species_context == "human"
    assert quality.origin_class == "HUMAN_CURATED"
    assert quality.source_quality == "curated"
    assert quality.sample_size_context == "known"
    assert quality.sample_size == 120


def test_derive_evidence_quality_detects_animal() -> None:
    evidence = ClaimEvidence(
        id=uuid4(),
        claim_id=uuid4(),
        snapshot_id=uuid4(),
        direction=EvidenceDirection.CONTRADICTORY,
        source_record_id="record-1",
        rationale="mouse model study",
    )
    quality = derive_evidence_quality(evidence)
    assert quality.species_context == "animal"
