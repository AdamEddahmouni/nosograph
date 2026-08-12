"""Reviewed legacy disease identifiers and Mondo mappings."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

from med_research.biomed.errors import BiomedicalValidationError
from med_research.diseases.base import Disease

LEGACY_DISEASE_MONDO_MAP: dict[str, str] = {
    "sle": "MONDO:0007915",
    "ra": "MONDO:0008390",
    "ms": "MONDO:0005217",
    "ss": "MONDO:0011604",
    "ssc": "MONDO:0005101",
    "t1d": "MONDO:0005147",
    "ibd": "MONDO:0005265",
}


@dataclass(frozen=True)
class LegacyDiseaseManifestEntry:
    legacy_id: str
    display_name: str
    mondo_curie: str


def legacy_disease_ids() -> list[str]:
    return sorted(LEGACY_DISEASE_MONDO_MAP)


def resolve_mondo_curie(disease_id: str) -> str:
    try:
        return LEGACY_DISEASE_MONDO_MAP[disease_id]
    except KeyError as exc:
        raise BiomedicalValidationError(
            f"Unknown legacy disease id {disease_id!r}; "
            f"expected one of {', '.join(legacy_disease_ids())}"
        ) from exc


def legacy_manifest_entry(disease_id: str) -> LegacyDiseaseManifestEntry:
    mondo_curie = resolve_mondo_curie(disease_id)
    disease = Disease(disease_id)
    return LegacyDiseaseManifestEntry(
        legacy_id=disease_id,
        display_name=disease.profile.name,
        mondo_curie=mondo_curie,
    )


def legacy_resource_version() -> str:
    return f"legacy-curated@{_git_commit_short()}"


def _git_commit_short() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    commit = result.stdout.strip()
    return commit or "unknown"
