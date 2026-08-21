"""Tests for centralized disease identifier resolution."""

import pytest

from med_research.diseases.identifiers import (
    CI_VALIDATED_DISEASES,
    REFERENCE_DISEASES,
    default_disease_for_selection,
    resolve_disease_identifier,
)


def test_resolve_alias_lupus_to_sle() -> None:
    assert resolve_disease_identifier("lupus") == "sle"
    assert resolve_disease_identifier("SLE") == "sle"


def test_resolve_rheumatoid_alias() -> None:
    assert resolve_disease_identifier("rheumatoid arthritis") == "ra"


def test_reference_diseases_exist() -> None:
    from med_research.diseases.base import Disease

    available = set(Disease.list_all())
    for did in REFERENCE_DISEASES:
        assert did in available


def test_ci_validated_count() -> None:
    assert len(CI_VALIDATED_DISEASES) == 8


def test_default_selection_not_hardcoded_sle_only() -> None:
    default = default_disease_for_selection()
    assert default
    from med_research.diseases.base import Disease

    assert default in Disease.list_all()


def test_unknown_identifier_raises() -> None:
    with pytest.raises(ValueError, match="unknown disease identifier"):
        resolve_disease_identifier("not_a_real_disease_xyz")
