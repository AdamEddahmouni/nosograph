"""Deterministic checksums for legacy disease data files."""

from __future__ import annotations

import hashlib
from pathlib import Path

from med_research.biomed.legacy.manifest import resolve_mondo_curie
from med_research.diseases.base import Disease

REQUIRED_DATA_FILES: tuple[str, ...] = (
    "profile.json",
    "genes.json",
    "drugs.json",
    "pathways.json",
    "relationships.json",
)


def legacy_file_checksums(disease_id: str) -> dict[str, str]:
    resolve_mondo_curie(disease_id)
    disease = Disease(disease_id)
    checksums: dict[str, str] = {}
    for filename in REQUIRED_DATA_FILES:
        path = disease.data_dir / filename
        checksums[filename] = _file_checksum(path)
    return checksums


def legacy_bundle_checksum(disease_ids: list[str]) -> str:
    digest = hashlib.sha256()
    for disease_id in sorted(disease_ids):
        digest.update(disease_id.encode())
        for filename in REQUIRED_DATA_FILES:
            digest.update(filename.encode())
            digest.update(legacy_file_checksums(disease_id)[filename].encode())
    return f"sha256:{digest.hexdigest()}"


def _file_checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"
