"""Legacy disease module projection into the canonical biomedical store."""

from med_research.biomed.legacy.adapter import LegacyMigrationAdapter
from med_research.biomed.legacy.compat import canonical_claim_count, legacy_projection_enabled
from med_research.biomed.legacy.manifest import LEGACY_DISEASE_MONDO_MAP, legacy_resource_version
from med_research.biomed.legacy.projector import project_disease
from med_research.biomed.legacy.report import ParityReport, build_parity_report

__all__ = [
    "LEGACY_DISEASE_MONDO_MAP",
    "LegacyMigrationAdapter",
    "ParityReport",
    "build_parity_report",
    "canonical_claim_count",
    "legacy_projection_enabled",
    "legacy_resource_version",
    "project_disease",
]
