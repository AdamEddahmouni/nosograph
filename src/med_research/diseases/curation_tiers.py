"""Formal curation tier definitions for the NosoGraph disease corpus."""

from __future__ import annotations

from typing import Any, Literal

from med_research.diseases.identifiers import CI_VALIDATED_DISEASES

CurationTier = Literal["scaffold", "L0", "L1", "L2", "L3", "ci_validated", "blocked"]

CURATION_TIER_DEFINITIONS: dict[str, str] = {
    "scaffold": (
        "Auto-generated module from public KBs; KG entities present but config "
        "may be incomplete. Not pipeline-ready without curation."
    ),
    "L0": "No usable knowledge-graph data (missing profile/genes/drugs/pathways/relationships).",
    "L1": "Partial KG and/or config gaps; strict validation fails.",
    "L2": "Strict validation pass — pipeline-ready curated corpus (~45 modules target).",
    "L3": "Research-ready deep corpus with expression consensus or equivalent depth (~23 modules).",
    "ci_validated": (
        "One of eight core modules (sle, ra, ms, ss, ssc, t1d, ibd, ad) validated "
        "with ``med-research disease validate --strict`` on every CI run."
    ),
    "blocked": "Non-disease slug or module load failure; excluded from pipeline use.",
}

FailureClass = Literal[
    "SCHEMA",
    "PROVENANCE",
    "IDENTIFIER",
    "MAPPING",
    "MISSING_REQUIRED_DATA",
    "LEGACY_FORMAT",
    "DANGLING_REFERENCE",
    "VALIDATOR_BUG",
    "SOURCE_VARIANCE",
]

FAILURE_CLASS_DEFINITIONS: dict[str, str] = {
    "SCHEMA": "JSON or pydantic schema validation failed for a KG or config artifact.",
    "PROVENANCE": "Missing or inconsistent source/provenance metadata.",
    "IDENTIFIER": "Unknown or unresolved disease identifier (slug, MONDO, EFO).",
    "MAPPING": "Cross-ontology or entity mapping failure.",
    "MISSING_REQUIRED_DATA": "Required config field or KG file absent or empty.",
    "LEGACY_FORMAT": "Deprecated field names or legacy-only data shapes.",
    "DANGLING_REFERENCE": "Relationship or config references an entity not in the module.",
    "VALIDATOR_BUG": "Validation rule misfire; fix the framework not the module.",
    "SOURCE_VARIANCE": "Upstream source drift; may be acceptable with review.",
}


def effective_curation_tier(readiness_tier: str, disease_id: str) -> str:
    """Map readiness tier (L0–L3/blocked) to display tier including CI-validated."""
    if disease_id in CI_VALIDATED_DISEASES and readiness_tier in ("L2", "L3"):
        return "ci_validated"
    return readiness_tier


def tier_summary_row(disease_id: str, readiness_tier: str, **extra: Any) -> dict[str, Any]:
    """Build a coverage-report row with formal tier metadata."""
    effective = effective_curation_tier(readiness_tier, disease_id)
    return {
        "disease_id": disease_id,
        "readiness_tier": readiness_tier,
        "curation_tier": effective,
        "ci_validated": disease_id in CI_VALIDATED_DISEASES,
        "tier_definition": CURATION_TIER_DEFINITIONS.get(
            effective, CURATION_TIER_DEFINITIONS.get(readiness_tier, "")
        ),
        **extra,
    }
