from __future__ import annotations

from pathlib import Path

from med_research.biomed.imports.mondo import MondoAdapter
from med_research.biomed.models import EntityType, MappingKind, Predicate, ResourcePolicy


def mondo_policy() -> ResourcePolicy:
    return ResourcePolicy(
        resource_name="mondo",
        license_id="CC-BY-4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        redistribution_policy="redistributable",
    )


def test_mondo_fixture_imports_condition_and_hierarchy() -> None:
    bundle = MondoAdapter().parse(
        Path("tests/fixtures/biomed/mondo/minimal.json"),
        policy=mondo_policy(),
    )
    curies = {rev.entity_id for rev in bundle.revisions}
    assert len(curies) >= 1
    primary_curies = {entity.primary_curie for entity in bundle.entities}
    assert "MONDO:0007915" in primary_curies
    predicates = {claim.predicate for claim in bundle.claims}
    assert Predicate.IS_A in predicates
    assert all(m.relation != MappingKind.EXACT or m.relation.can_auto_join for m in bundle.mappings)


def test_mondo_revision_types_are_conditions() -> None:
    bundle = MondoAdapter().parse(
        Path("tests/fixtures/biomed/mondo/minimal.json"),
        policy=mondo_policy(),
    )
    assert all(entity.entity_type == EntityType.CONDITION for entity in bundle.entities)


def test_mondo_obsolete_term_preserved() -> None:
    bundle = MondoAdapter().parse(
        Path("tests/fixtures/biomed/mondo/minimal.json"),
        policy=mondo_policy(),
    )
    obsolete = [rev for rev in bundle.revisions if rev.obsolete]
    assert obsolete
    assert obsolete[0].consider or obsolete[0].replaced_by


def test_mondo_slim_skips_hierarchy_claims() -> None:
    full = MondoAdapter().parse(
        Path("tests/fixtures/biomed/mondo/minimal.json"),
        policy=mondo_policy(),
        slim=False,
    )
    slim = MondoAdapter().parse(
        Path("tests/fixtures/biomed/mondo/minimal.json"),
        policy=mondo_policy(),
        slim=True,
    )
    assert any(claim.predicate == Predicate.IS_A for claim in full.claims)
    assert not slim.claims
