from med_research.biomed.models import Predicate
from med_research.web.services.universal_service import (
    get_condition,
    list_condition_claims,
    search_conditions,
)


def test_get_condition_returns_mappings_and_active_snapshots(biomed_repository) -> None:
    summary = get_condition(biomed_repository, "MONDO:0007915")
    assert summary is not None
    assert summary.curie == "MONDO:0007915"
    assert summary.disclaimer.text
    assert summary.snapshots


def test_list_claims_supports_predicate_filter(biomed_repository) -> None:
    page = list_condition_claims(
        biomed_repository, "MONDO:0007915", predicate=Predicate.HAS_PHENOTYPE
    )
    assert page.items
    assert all(item.predicate == Predicate.HAS_PHENOTYPE.value for item in page.items)


def test_search_conditions_finds_lupus(biomed_repository) -> None:
    page = search_conditions(biomed_repository, "lupus", limit=5)
    assert page.total >= 1
    assert any("lupus" in item.label.lower() for item in page.items)
