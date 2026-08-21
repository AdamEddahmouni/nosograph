"""Batch strict validation with machine-readable failure classification."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from med_research.diseases.base import Disease
from med_research.diseases.corpus_status import build_corpus_status
from med_research.diseases.curation_tiers import (
    FAILURE_CLASS_DEFINITIONS,
    FailureClass,
)
from med_research.diseases.identifiers import CI_VALIDATED_DISEASES, REFERENCE_DISEASES
from med_research.diseases.registry_quality import is_blocked_slug
from med_research.diseases.tier_model import KG_FIELDS

TierFilter = Literal["L2", "L3", "ci_validated", "reference", "all"]

KG_FIELD_SET = frozenset(KG_FIELDS)
CONFIG_PREFIXES = (
    "SYMPTOMS",
    "PUBMED_QUERIES",
    "TRIAL_QUERY",
    "GWAS_SEARCH_TERMS",
    "CAR_T_SCORES",
    "DRUG_SAFETY_RISK",
)


def classify_failure(field: str, status: str) -> FailureClass:
    """Map a validation field/status pair to a failure class."""
    if status == "ok":
        raise ValueError("cannot classify passing check")

    lowered = status.lower()
    if lowered.startswith("invalid"):
        if "legacy" in lowered or "lupus_evidence" in lowered or "sle_evidence" in lowered:
            return "LEGACY_FORMAT"
        return "SCHEMA"

    if field in KG_FIELD_SET:
        if lowered == "missing":
            return "MISSING_REQUIRED_DATA"
        return "SCHEMA"

    if field in CONFIG_PREFIXES:
        if lowered in ("missing", "empty"):
            return "MISSING_REQUIRED_DATA"
        return "MAPPING"

    if "provenance" in lowered or "source" in lowered:
        return "PROVENANCE"

    if "dangling" in lowered or "unknown entity" in lowered:
        return "DANGLING_REFERENCE"

    if "identifier" in lowered or "efo" in lowered or "mondo" in lowered:
        return "IDENTIFIER"

    return "MISSING_REQUIRED_DATA"


def _disease_ids_for_filter(tier_filter: TierFilter) -> list[str]:
    if tier_filter == "reference":
        return list(REFERENCE_DISEASES)
    if tier_filter == "ci_validated":
        return sorted(CI_VALIDATED_DISEASES)

    if tier_filter == "all":
        return sorted(Disease.list_all())

    from med_research.diseases.corpus_status import DEFAULT_STATUS_PATH, load_status_report

    status = load_status_report(DEFAULT_STATUS_PATH)
    if status.get("per_disease"):
        tier_key = tier_filter.upper()
        return sorted(
            row["disease_id"]
            for row in status["per_disease"]
            if row.get("tier") == tier_key and not is_blocked_slug(row["disease_id"])
        )

    # Fallback when no cached status report exists yet.
    live_status = build_corpus_status(include_symptom_source=False)
    tier_key = tier_filter.upper()
    return sorted(
        row["disease_id"]
        for row in live_status["per_disease"]
        if row.get("tier") == tier_key and not is_blocked_slug(row["disease_id"])
    )


def run_strict_validation_batch(
    *,
    tier_filter: TierFilter = "L2",
    limit: int | None = None,
    disease_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Validate a corpus slice and emit classified failures."""
    targets = disease_ids or _disease_ids_for_filter(tier_filter)
    if limit is not None:
        targets = targets[:limit]

    entries: list[dict[str, Any]] = []
    failure_counts: dict[str, int] = {key: 0 for key in FAILURE_CLASS_DEFINITIONS}
    passed = 0
    failed = 0

    for did in targets:
        if is_blocked_slug(did):
            failed += 1
            failure_counts["IDENTIFIER"] += 1
            entries.append(
                {
                    "disease_id": did,
                    "passed": False,
                    "failures": [{"field": "slug", "status": "blocked", "class": "IDENTIFIER"}],
                }
            )
            continue

        try:
            disease = Disease(did)
            checks = disease.validate()
            name = disease.profile.name
        except Exception as exc:
            failed += 1
            failure_counts["VALIDATOR_BUG"] += 1
            entries.append(
                {
                    "disease_id": did,
                    "name": did,
                    "passed": False,
                    "failures": [{"field": "module", "status": str(exc), "class": "VALIDATOR_BUG"}],
                }
            )
            continue

        bad = {field: status for field, status in checks.items() if status != "ok"}
        if not bad:
            passed += 1
            entries.append({"disease_id": did, "name": name, "passed": True, "failures": []})
            continue

        failed += 1
        failures = []
        for field, status in bad.items():
            failure_class = classify_failure(field, status)
            failure_counts[failure_class] += 1
            failures.append({"field": field, "status": status, "class": failure_class})
        entries.append({"disease_id": did, "name": name, "passed": False, "failures": failures})

    total = len(targets)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tier_filter": tier_filter,
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": round(passed / max(total, 1), 4),
            "failure_classes": {k: v for k, v in failure_counts.items() if v},
        },
        "failure_class_definitions": FAILURE_CLASS_DEFINITIONS,
        "entries": entries,
    }


def write_validation_report(
    report: dict[str, Any],
    path: Path | None = None,
) -> Path:
    """Persist a validation batch report as JSON."""
    root = Path(__file__).resolve().parents[3]
    out = path or (root / "data" / "reports" / "validation_batch_report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out
