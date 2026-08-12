import pytest

from med_research.biomed.identifiers import (
    canonical_json,
    claim_uuid,
    entity_uuid,
    fingerprint_json,
    normalize_curie,
)
from med_research.biomed.models import EntityType, MappingKind, Predicate


def test_normalization_and_ids_are_stable() -> None:
    assert normalize_curie(" mondo:0007915 ") == "MONDO:0007915"
    assert entity_uuid(EntityType.CONDITION, "mondo:0007915") == entity_uuid(
        EntityType.CONDITION, "MONDO:0007915"
    )
    left = claim_uuid("MONDO:0007915", Predicate.HAS_PHENOTYPE, "HP:0001945", {"negated": False})
    right = claim_uuid("mondo:0007915", Predicate.HAS_PHENOTYPE, "hp:0001945", {"negated": False})
    assert left == right


def test_invalid_curie_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Invalid CURIE"):
        normalize_curie("invalid_curie_without_prefix")

    with pytest.raises(ValueError, match="Invalid CURIE"):
        normalize_curie("MONDO: 0007915")


def test_only_exact_mapping_can_auto_join() -> None:
    assert MappingKind.EXACT.can_auto_join is True
    assert MappingKind.CLOSE.can_auto_join is False
    assert MappingKind.BROAD.can_auto_join is False
    assert MappingKind.NARROW.can_auto_join is False


def test_canonical_json_and_fingerprint() -> None:
    data1 = {"b": 2, "a": 1}
    data2 = {"a": 1, "b": 2}
    assert canonical_json(data1) == canonical_json(data2)
    assert canonical_json(data1) == '{"a":1,"b":2}'
    assert fingerprint_json(data1) == fingerprint_json(data2)
