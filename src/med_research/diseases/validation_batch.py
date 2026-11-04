"""Batch strict validation with machine-readable failure classification."""

from __future__ import annotations

import hashlib
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
from med_research.diseases.evidence_gate import (
    EVIDENCE_DENSITY_TARGET,
    assess_disease,
    summarize_evidence,
)
from med_research.diseases.identifiers import CI_VALIDATED_DISEASES, REFERENCE_DISEASES
from med_research.diseases.registry_quality import is_blocked_slug
from med_research.diseases.tier_model import KG_FIELDS

TierFilter = Literal["L2", "L3", "ci_validated", "reference", "all"]

# Process exit codes for the validation CLI paths. Part of the command contract.
EXIT_OK = 0
EXIT_VALIDATION_FAILED = 1
EXIT_USAGE = 2

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


def _deterministic_sample(ids: list[str], *, sample_size: int, sample_seed: int) -> list[str]:
    """Return a version-stable sample ordered by a seeded content hash.

    ``random.sample`` is intentionally avoided: hash ordering of
    ``sha256(f"{seed}:{disease_id}")`` is reproducible across processes,
    platforms, and Python versions.
    """
    if sample_size <= 0:
        return []
    ordered = sorted(
        ids,
        key=lambda disease_id: hashlib.sha256(f"{sample_seed}:{disease_id}".encode()).hexdigest(),
    )
    return ordered[:sample_size]


def select_validation_targets(
    *,
    tier_filter: TierFilter = "L2",
    limit: int | None = None,
    disease_ids: list[str] | None = None,
    sample_size: int | None = None,
    sample_seed: int = 0,
) -> tuple[list[str], int]:
    """Resolve the validation target list and count excluded blocked slugs.

    Selection order is: tier/explicit list → blocked-slug exclusion →
    deterministic sample (when ``sample_size`` is set) → ``limit`` cap.
    Explicit ``disease_ids`` keep caller order, and tier filters keep their
    existing stable order, so report ordering never depends on dict order.
    Sampling reorders the surviving candidates by seeded hash.
    """
    if disease_ids is not None:
        candidates: list[str] = []
        seen: set[str] = set()
        for disease_id in disease_ids:
            if disease_id in seen:
                continue
            seen.add(disease_id)
            candidates.append(disease_id)
    else:
        # Tier filters already return a stable order; keep it so report ordering
        # stays compatible with pre-sampling behaviour.
        candidates = list(_disease_ids_for_filter(tier_filter))

    excluded_blocked = sum(1 for disease_id in candidates if is_blocked_slug(disease_id))
    candidates = [disease_id for disease_id in candidates if not is_blocked_slug(disease_id)]

    if sample_size is not None:
        candidates = _deterministic_sample(
            candidates, sample_size=sample_size, sample_seed=sample_seed
        )

    if limit is not None:
        candidates = candidates[: max(limit, 0)]

    return candidates, excluded_blocked


def run_strict_validation_batch(
    *,
    tier_filter: TierFilter = "L2",
    limit: int | None = None,
    disease_ids: list[str] | None = None,
    sample_size: int | None = None,
    sample_seed: int = 0,
    include_evidence: bool = True,
    require_evidence: bool = False,
) -> dict[str, Any]:
    """Validate a corpus slice and emit structural and evidence results separately.

    ``passed`` remains the structural validation result for compatibility. A
    module is ``evidenced`` only when at least
    :data:`~med_research.diseases.evidence_gate.EVIDENCE_DENSITY_TARGET` of its
    gene, drug, and pathway records carry a resolvable identifier. The two
    results never collapse into one another: a structurally valid module can
    be unevidenced, and a structurally broken module can still be evidenced.
    """
    targets, excluded_blocked = select_validation_targets(
        tier_filter=tier_filter,
        limit=limit,
        disease_ids=disease_ids,
        sample_size=sample_size,
        sample_seed=sample_seed,
    )

    entries: list[dict[str, Any]] = []
    failure_counts: dict[str, int] = {key: 0 for key in FAILURE_CLASS_DEFINITIONS}
    failure_groups: dict[str, int] = {}
    structurally_valid = 0
    structurally_failed = 0
    evidence_assessed = 0
    evidenced = 0
    evidence_records = 0
    evidence_with_identifiers = 0

    def record_failure(field: str, status: str, failure_class: FailureClass) -> dict[str, str]:
        failure_counts[failure_class] += 1
        failure_groups[field] = failure_groups.get(field, 0) + 1
        return {"field": field, "status": status, "class": failure_class}

    for did in targets:
        try:
            disease = Disease(did)
            checks = disease.validate()
            name = disease.profile.name
        except Exception as exc:
            structurally_failed += 1
            evidence = summarize_evidence(
                0,
                0,
                structurally_valid=False,
                assessed=False,
                errors={"module": f"{type(exc).__name__}: {exc}"},
            )
            entries.append(
                {
                    "disease_id": did,
                    "name": did,
                    "passed": False,
                    "structurally_valid": False,
                    "evidenced": False,
                    "failures": [record_failure("module", str(exc), "VALIDATOR_BUG")],
                    "evidence": evidence,
                }
            )
            continue

        bad = {field: status for field, status in checks.items() if status != "ok"}
        strict_pass = not bad
        failures = [
            record_failure(field, status, classify_failure(field, status))
            for field, status in bad.items()
        ]
        if strict_pass:
            structurally_valid += 1
        else:
            structurally_failed += 1

        if include_evidence:
            evidence = assess_disease(disease)
        else:
            evidence = summarize_evidence(
                0,
                0,
                structurally_valid=strict_pass,
                assessed=False,
            )
        evidence["structurally_valid"] = strict_pass

        if evidence.get("assessed"):
            evidence_assessed += 1
            evidence_records += int(evidence["records"])
            evidence_with_identifiers += int(evidence["evidenced"])
            if evidence["passes"]:
                evidenced += 1

        entries.append(
            {
                "disease_id": did,
                "name": name,
                "passed": strict_pass,
                "structurally_valid": strict_pass,
                "evidenced": bool(evidence["passes"]) if evidence.get("assessed") else None,
                "failures": failures,
                "evidence": evidence,
            }
        )

    total = len(targets)
    overall_evidence = summarize_evidence(
        evidence_records,
        evidence_with_identifiers,
        structurally_valid=total > 0 and structurally_valid == total,
    )
    evidence_gate_passed = (
        bool(include_evidence) and total > 0 and evidence_assessed == total and evidenced == total
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tier_filter": tier_filter,
        "summary": {
            "total": total,
            "passed": structurally_valid,
            "failed": structurally_failed,
            "pass_rate": round(structurally_valid / max(total, 1), 4),
            "structurally_valid": structurally_valid,
            "structurally_failed": structurally_failed,
            "evidenced": evidenced,
            "not_evidenced": evidence_assessed - evidenced,
            "evidence_assessed": evidence_assessed,
            "evidence_target": EVIDENCE_DENSITY_TARGET,
            "evidence_density": overall_evidence["density"],
            "evidence_gate_enabled": require_evidence,
            "evidence_gate_passed": evidence_gate_passed if include_evidence else None,
            "sampled": sample_size is not None,
            "sample_size": sample_size,
            "sample_seed": sample_seed,
            "excluded_blocked": excluded_blocked,
            "failure_classes": {k: v for k, v in failure_counts.items() if v},
            "failure_groups": dict(
                sorted(failure_groups.items(), key=lambda item: (-item[1], item[0]))
            ),
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
