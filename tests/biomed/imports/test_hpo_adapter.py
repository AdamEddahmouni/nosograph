from __future__ import annotations

from pathlib import Path

from med_research.biomed.imports.hpo import HpoOntologyAdapter
from med_research.biomed.models import EntityType, Predicate, ResourcePolicy


def hpo_policy() -> ResourcePolicy:
    return ResourcePolicy(
        resource_name="hp",
        license_id="custom",
        license_url="https://hpo.jax.org/app/license",
        redistribution_policy="user_supplied",
    )


def test_hpo_fixture_imports_phenotype_hierarchy() -> None:
    bundle = HpoOntologyAdapter().parse(
        Path("tests/fixtures/biomed/hpo/minimal.json"),
        policy=hpo_policy(),
    )
    assert any(entity.entity_type == EntityType.PHENOTYPE for entity in bundle.entities)
    child = next(c for c in bundle.claims if c.predicate == Predicate.IS_A)
    assert child.subject_curie != child.object_curie


def test_hpo_upstream_version_from_fixture_metadata() -> None:
    bundle = HpoOntologyAdapter().parse(
        Path("tests/fixtures/biomed/hpo/minimal.json"),
        policy=hpo_policy(),
    )
    assert bundle.snapshot.upstream_version == "2024-02-15"
