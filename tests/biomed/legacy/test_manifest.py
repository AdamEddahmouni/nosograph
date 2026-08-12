from __future__ import annotations

import pytest

DISEASES = ["sle", "ra", "ms", "ss", "ssc", "t1d", "ibd"]


@pytest.mark.parametrize("disease_id", DISEASES)
def test_every_legacy_disease_has_reviewed_mondo_mapping(disease_id: str) -> None:
    from med_research.biomed.legacy.manifest import LEGACY_DISEASE_MONDO_MAP

    assert disease_id in LEGACY_DISEASE_MONDO_MAP
    assert LEGACY_DISEASE_MONDO_MAP[disease_id].startswith("MONDO:")


def test_legacy_checksums_cover_required_data_files() -> None:
    from med_research.biomed.legacy.checksums import legacy_file_checksums

    checksums = legacy_file_checksums("sle")
    assert set(checksums) >= {
        "profile.json",
        "genes.json",
        "drugs.json",
        "pathways.json",
        "relationships.json",
    }


def test_unknown_disease_rejected() -> None:
    from med_research.biomed.errors import BiomedicalValidationError
    from med_research.biomed.legacy.manifest import resolve_mondo_curie

    with pytest.raises(BiomedicalValidationError):
        resolve_mondo_curie("unknown")
