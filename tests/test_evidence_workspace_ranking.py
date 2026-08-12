from datetime import date

import pytest

from med_research.pipeline.evidence_workspace.ranking import rank_drugs, rank_targets
from med_research.pipeline.evidence_workspace.schemas import Citation, Claim, EvidenceRecord

pytestmark = pytest.mark.unit


def _evidence(source="pubmed", evidence_type="RCT", year=2024):
    return EvidenceRecord(
        evidence_id=f"{source}:1",
        source=source,
        native_id="1",
        title="JAK evidence",
        url="https://example.org/1",
        published_date=date(year, 1, 1),
        evidence_type=evidence_type,
    )


def _claim(subject_id, subject_type, relationship, evidence_id, confidence=0.9):
    return Claim(
        claim_id=f"{relationship}:{subject_id}:{evidence_id}",
        subject_id=subject_id,
        subject_type=subject_type,
        subject_name=subject_id,
        relationship=relationship,
        text="Evidence claim",
        evidence_ids=[evidence_id],
        citations=[Citation(source="pubmed", native_id="1", url="https://example.org/1")],
        confidence=confidence,
        extraction_method="rules",
    )


def test_supporting_and_clinical_evidence_ranks_drug():
    records = [_evidence("clinical_trials", "PHASE3")]
    ranked = rank_drugs(records, [_claim("baricitinib", "drug", "supports", "clinical_trials:1")])

    assert ranked[0].candidate_id == "baricitinib"
    assert ranked[0].component_scores["clinical_trial"] > 0
    assert ranked[0].score > 0


def test_contradiction_lowers_score_and_targets_are_separate():
    records = [_evidence(), _evidence("clinical_trials", "PHASE3", 2020)]
    claims = [
        _claim("JAK1", "target", "supports", "pubmed:1"),
        _claim("JAK1", "target", "contradicts", "clinical_trials:1"),
    ]
    ranked = rank_targets(records, claims)

    assert ranked[0].candidate_type == "target"
    assert ranked[0].contradicting_claim_ids
    assert ranked[0].component_scores["contradiction_penalty"] > 0
