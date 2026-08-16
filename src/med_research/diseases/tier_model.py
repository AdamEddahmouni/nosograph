"""Disease corpus readiness tier model (L0–L3)."""

from __future__ import annotations

from typing import Any

from med_research.diseases.registry_quality import is_blocked_slug
from med_research.pipeline.gene_expression.geo import CURATED_CONSENSUS_DISEASES

KG_FIELDS = ("genes", "drugs", "pathways", "relationships", "profile")
CONFIG_FIELDS = (
    "SYMPTOMS",
    "PUBMED_QUERIES",
    "TRIAL_QUERY",
    "GWAS_SEARCH_TERMS",
    "CAR_T_SCORES",
    "DRUG_SAFETY_RISK",
)


def _has_kg_data(checks: dict[str, str]) -> bool:
    return all(checks.get(field) == "ok" for field in KG_FIELDS)


def _config_gaps(checks: dict[str, str], *, drug_count: int) -> list[str]:
    gaps: list[str] = []
    for field in CONFIG_FIELDS:
        status = checks.get(field, "missing")
        if status == "ok":
            continue
        if field == "DRUG_SAFETY_RISK" and drug_count == 0:
            continue
        gaps.append(field)
    return gaps


def compute_tier(
    disease_id: str,
    checks: dict[str, str],
    *,
    drug_count: int = 0,
    strict_pass: bool | None = None,
) -> str:
    """Assign L0–L3 tier for a disease module."""
    if is_blocked_slug(disease_id):
        return "blocked"

    if disease_id in CURATED_CONSENSUS_DISEASES:
        return "L3"

    if not _has_kg_data(checks):
        if any(checks.get(f) == "ok" for f in KG_FIELDS):
            return "L1"
        return "L0"

    gaps = _config_gaps(checks, drug_count=drug_count)
    if strict_pass is None:
        strict_pass = not gaps and all(
            checks.get(f) == "ok"
            for f in CONFIG_FIELDS
            if f != "DRUG_SAFETY_RISK" or drug_count > 0
        )

    if strict_pass and not gaps:
        return "L2"
    if gaps:
        return "L1"
    return "L2"


def aggregate_tiers(per_disease: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"L0": 0, "L1": 0, "L2": 0, "L3": 0, "blocked": 0}
    for row in per_disease:
        tier = row.get("tier", "blocked")
        if tier not in counts:
            counts["blocked"] += 1
        else:
            counts[tier] += 1
    return counts
