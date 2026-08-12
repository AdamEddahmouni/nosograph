"""Compatibility helpers for optional canonical legacy projections."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from med_research.biomed.legacy.manifest import resolve_mondo_curie

if TYPE_CHECKING:
    from med_research.biomed.repository import BiomedicalRepository


def legacy_projection_enabled(repository: BiomedicalRepository) -> bool:
    if os.environ.get("BIOMED_LEGACY_PROJECTION") != "1":
        return False
    return repository.get_active_snapshot("legacy-curated") is not None


def canonical_claim_count(repository: BiomedicalRepository, disease_id: str) -> int:
    mondo_curie = resolve_mondo_curie(disease_id)
    claims = repository.list_claims(mondo_curie)
    return len(claims)
