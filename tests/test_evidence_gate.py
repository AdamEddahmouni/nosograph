"""Contract tests for the evidence-density gate.

The gate is intentionally narrow: it asks whether a gene, drug, or pathway
record declares at least one resolvable external identifier. It does not
dereference the identifier and it does not turn structural validity into an
evidence claim.
"""

from __future__ import annotations

import pytest

from med_research.diseases.base import Disease
from med_research.diseases.evidence_gate import (
    EVIDENCE_DENSITY_TARGET,
    assess_disease,
    assess_records,
    is_resolvable_reference,
    reference_schemes,
    summarize_evidence,
)
from med_research.diseases.identifiers import CI_VALIDATED_DISEASES, REFERENCE_DISEASES
from med_research.diseases.validation_batch import run_strict_validation_batch

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("reference", "expected"),
    [
        ("PMID:12345678", True),
        ("DOI:10.1000/example", True),
        ("CLINVAR:12345", True),
        ("Trial registry entry (NCT04252599)", True),
        ("curator note without an identifier", False),
        ("PMID", False),
        ("", False),
    ],
)
def test_resolvable_identifier_detection(reference: str, expected: bool) -> None:
    assert is_resolvable_reference(reference) is expected


def test_free_text_reference_is_not_counted_as_provenance() -> None:
    assert reference_schemes("curator note without an identifier") == ["UNCLASSIFIED"]
    assert reference_schemes("PMID:12345678") == ["PMID"]


def test_record_id_is_not_evidence() -> None:
    summary = assess_records(
        {
            "genes": [
                {"id": "PMID:12345678"},
                {"id": "G2", "references": ["PMID:87654321"]},
            ]
        }
    )

    assert summary["records"] == 2
    assert summary["evidenced"] == 1
    assert summary["by_collection"]["genes"]["density"] == 0.5


def test_zero_records_cannot_pass() -> None:
    summary = summarize_evidence(0, 0)

    assert summary["density"] == 0.0
    assert summary["passes"] is False


def test_free_text_only_collection_fails_density_gate() -> None:
    summary = assess_records(
        {
            "genes": [
                {"id": "G1", "references": ["curator note"]},
                {"id": "G2", "references": []},
                {"id": "G3"},
            ]
        }
    )

    assert summary["records"] == 3
    assert summary["evidenced"] == 0
    assert summary["passes"] is False


@pytest.mark.parametrize("disease_ids", [REFERENCE_DISEASES, CI_VALIDATED_DISEASES])
def test_reference_and_ci_sets_meet_density_target(disease_ids: tuple[str, ...]) -> None:
    total = 0
    evidenced = 0
    for disease_id in disease_ids:
        evidence = assess_disease(Disease(disease_id))
        assert evidence["assessed"] is True
        assert evidence["records"] > 0
        assert evidence["density"] >= EVIDENCE_DENSITY_TARGET
        assert evidence["passes"] is True
        total += evidence["records"]
        evidenced += evidence["evidenced"]

    assert total > 0
    assert evidenced / total >= EVIDENCE_DENSITY_TARGET


def test_structural_and_evidence_results_are_reported_separately() -> None:
    report = run_strict_validation_batch(
        tier_filter="reference",
        require_evidence=True,
    )
    summary = report["summary"]

    assert summary["structurally_valid"] == summary["total"]
    assert summary["evidenced"] == summary["evidence_assessed"] == summary["total"]
    assert summary["evidence_gate_passed"] is True
    for entry in report["entries"]:
        assert entry["structurally_valid"] is entry["passed"] is True
        assert entry["evidenced"] is True
        assert entry["evidence"]["structurally_valid"] is True


def test_evidence_assessment_can_be_disabled_without_faking_a_pass() -> None:
    report = run_strict_validation_batch(
        tier_filter="reference",
        include_evidence=False,
        require_evidence=False,
    )
    summary = report["summary"]

    assert summary["evidence_assessed"] == 0
    assert summary["evidence_gate_passed"] is None
    assert all(entry["evidenced"] is None for entry in report["entries"])
