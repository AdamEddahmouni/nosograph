"""Tests for registry quality admission gates."""

from med_research.diseases.registry_quality import (
    filter_disease_entries,
    is_blocked_slug,
    is_disease_like_entry,
    looks_like_go_process_slug,
)


def test_blocked_slugs() -> None:
    assert is_blocked_slug("positive_regulation_of_ovulation")
    assert looks_like_go_process_slug("response_to_stimulus")
    assert not is_blocked_slug("sle")


def test_disease_like_entry_requires_identifier_or_name() -> None:
    assert is_disease_like_entry(
        {"id": "ra", "name": "Rheumatoid arthritis", "efo_id": "EFO_0000685"}
    )
    assert not is_disease_like_entry(
        {"id": "positive_regulation_of_ovulation", "name": "process", "efo_id": "EFO_1"}
    )


def test_filter_disease_entries() -> None:
    entries = [
        {"id": "sle", "name": "SLE", "efo_id": "EFO_0002691"},
        {"id": "positive_regulation_of_ovulation", "name": "process", "efo_id": "EFO_1"},
    ]
    kept, rejected = filter_disease_entries(entries)
    assert len(kept) == 1
    assert rejected == ["positive_regulation_of_ovulation"]
