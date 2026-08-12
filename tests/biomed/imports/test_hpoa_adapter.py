from __future__ import annotations

from pathlib import Path

from med_research.biomed.imports.hpoa import HpoAnnotationAdapter
from med_research.biomed.models import EvidenceDirection, Predicate, ResourcePolicy


def hpoa_policy() -> ResourcePolicy:
    return ResourcePolicy(
        resource_name="hpoa",
        license_id="custom",
        license_url="https://hpo.jax.org/app/license",
        redistribution_policy="user_supplied",
    )


def test_hpoa_preserves_frequency_and_negation() -> None:
    bundle = HpoAnnotationAdapter().parse(
        Path("tests/fixtures/biomed/hpoa/minimal.tsv"),
        policy=hpoa_policy(),
        mondo_mappings={"OMIM:152700": "MONDO:0007915"},
    )
    claim = next(c for c in bundle.claims if c.predicate == Predicate.HAS_PHENOTYPE)
    assert claim.qualifiers.get("frequency") == "Very frequent"
    assert claim.qualifiers.get("negated") is False
    evidence = bundle.evidence[0]
    assert evidence.direction in {EvidenceDirection.SUPPORTING, EvidenceDirection.CONTRADICTORY}


def test_hpoa_unresolved_disease_is_reported_not_joined() -> None:
    bundle = HpoAnnotationAdapter().parse(
        Path("tests/fixtures/biomed/hpoa/minimal.tsv"),
        policy=hpoa_policy(),
        mondo_mappings={},
    )
    codes = {warning.code for warning in bundle.warnings}
    assert "unresolved_disease_mapping" in codes
