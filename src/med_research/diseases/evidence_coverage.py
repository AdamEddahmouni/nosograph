"""Evidence coverage and provenance inspection for the disease corpus.

This module answers a narrower question than "is this disease well researched?":
*what evidence does a module record, and does that evidence carry provenance?*
It deliberately never converts missingness into a quality score. A module with
no recorded citation is not a module proven to lack support, and a module with
many citations is not a module whose claims were verified.

Two distinctions carry the whole report:

``present`` / ``known_absent`` / ``not_recorded`` / ``invalid``
    ``present`` means the field exists with content. ``known_absent`` means the
    curator recorded an explicitly empty value (``"references": []``), which is
    a deliberate statement. ``not_recorded`` means the key is absent, so nothing
    was ever asserted either way. ``invalid`` means the artifact could not be
    read, which is a defect rather than an absence.

corpus sampling versus full population
    The checked-out registry holds thousands of scaffold modules. A report over
    a bounded slice is a *sample*: :func:`build_evidence_coverage_report` states
    the population size and never lets a sampled figure be read as a
    full-corpus measurement.

Output is canonical JSON with a content fingerprint that excludes the
generation timestamp, so two runs over identical inputs produce identical
fingerprints even though ``generated_at`` differs.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Sequence, cast

from med_research.diseases.base import Disease
from med_research.diseases.curation_state import (
    GENERATOR_MARKER,
    SCAFFOLD_MARKER,
    classify_curation_state,
)
from med_research.diseases.curation_tiers import (
    FAILURE_CLASS_DEFINITIONS,
    tier_summary_row,
)
from med_research.diseases.evidence_gate import (
    EVIDENCE_DENSITY_TARGET,
    KNOWN_REFERENCE_SCHEMES,
    is_resolvable_reference,
    summarize_evidence,
)
from med_research.diseases.evidence_gate import reference_schemes as _reference_schemes
from med_research.diseases.identifiers import REFERENCE_DISEASES
from med_research.diseases.registry_quality import is_blocked_slug
from med_research.diseases.tier_model import compute_tier
from med_research.diseases.validation_batch import classify_failure

REPORT_SCHEMA = "nosograph.evidence_coverage/1"

#: Default slice: the diverse reference diseases (autoimmune, Mendelian,
#: infectious, neoplastic, neurodegenerative, metabolic). Bounded on purpose.
DEFAULT_DISEASE_IDS: tuple[str, ...] = tuple(REFERENCE_DISEASES)

PresenceState = Literal["present", "known_absent", "not_recorded", "invalid"]
CategoryState = PresenceState

#: Generator markers live in :mod:`med_research.diseases.curation_state`, which
#: both this report and the corpus browser use so the two can never disagree.
#: Re-exported here for report consumers.


#: Recognised identifier schemes are defined in
#: :mod:`med_research.diseases.evidence_gate`, so the report and the validation
#: gate can never disagree about what counts as provenance.

#: Cap on per-disease unprovenanced record listings, so a large module cannot
#: produce an unbounded report. The aggregate counts are never capped.
UNPROVENANCED_LIST_LIMIT = 25


@dataclass(frozen=True)
class _RecordCategory:
    """A data-file collection whose records may carry record-level provenance."""

    key: str
    label: str
    filename: str
    collection: str
    accessor: str
    provenance_field: str | None


@dataclass(frozen=True)
class _ConfigCategory:
    """A disease-config value that acts as a curated input."""

    key: str
    label: str
    config_key: str


_RECORD_CATEGORIES: tuple[_RecordCategory, ...] = (
    _RecordCategory(
        key="genetics",
        label="Gene associations",
        filename="genes.json",
        collection="genes",
        accessor="load_genes",
        provenance_field="references",
    ),
    _RecordCategory(
        key="pharmacology",
        label="Drug records",
        filename="drugs.json",
        collection="drugs",
        accessor="load_drugs",
        provenance_field="references",
    ),
    _RecordCategory(
        key="pathways",
        label="Pathway records",
        filename="pathways.json",
        collection="pathways",
        accessor="load_pathways",
        provenance_field="references",
    ),
    _RecordCategory(
        key="relationships",
        label="Knowledge-graph relationships",
        filename="relationships.json",
        collection="relationships",
        accessor="load_relationships",
        # The relationship schema defines no citation field: these edges are
        # structural assertions, so their provenance is not applicable rather
        # than missing. Counting them as gaps would inflate the defect rate.
        provenance_field=None,
    ),
)

_CONFIG_CATEGORIES: tuple[_ConfigCategory, ...] = (
    _ConfigCategory("phenotype", "Phenotype terms", "SYMPTOMS"),
    _ConfigCategory("literature", "Literature queries", "PUBMED_QUERIES"),
    _ConfigCategory("trials", "Trial query", "TRIAL_QUERY"),
    _ConfigCategory("gwas_terms", "GWAS search terms", "GWAS_SEARCH_TERMS"),
    _ConfigCategory("safety_risk", "Disease-specific safety risk", "DISEASE_SPECIFIC_RISK"),
)

_MEASUREMENT_LIMITATIONS: tuple[str, ...] = (
    "Provenance counts recorded references only; absence means NosoGraph holds no "
    "recorded citation for that record, not that no evidence exists.",
    "A reference identifier is never dereferenced, so a recorded citation is not a "
    "verified citation and support is not assessed here.",
    "Reference presence is not evidence quality: a single PMID and a systematic "
    "review are counted identically.",
    "Relationship edges carry no citation field in the current schema, so their "
    "provenance is reported as not-applicable instead of as a gap.",
    "Config-derived categories can only be present or known-absent: the scaffold "
    "template defines every config key, so 'never recorded' is indistinguishable "
    "from 'recorded empty' for those fields.",
    "A bounded run measures a sample of the registry. Compare it only against runs "
    "that used the same selection.",
)


def _presence_state(value: Any) -> PresenceState:
    """Classify a config value, preserving the empty-versus-absent distinction."""
    if value is None:
        return "not_recorded"
    if isinstance(value, (str, bytes, list, tuple, set, dict)):
        return "present" if value else "known_absent"
    return "present"


def _load_records(disease: Disease, category: _RecordCategory) -> tuple[CategoryState, list[dict]]:
    """Load a data-file collection and classify its presence."""
    path = disease.data_dir / category.filename
    if not path.is_file():
        return "not_recorded", []
    try:
        payload = getattr(disease, category.accessor)()
    except (OSError, ValueError, TypeError, KeyError):
        return "invalid", []
    if not isinstance(payload, dict):
        return "invalid", []
    if category.collection not in payload:
        return "not_recorded", []
    items = payload.get(category.collection)
    if not isinstance(items, list):
        return "invalid", []
    if not items:
        return "known_absent", []
    return "present", [item for item in items if isinstance(item, dict)]


def _provenance_summary(records: list[dict], field: str) -> dict[str, Any]:
    """Summarise record-level provenance for one collection."""
    counts = {"present": 0, "known_absent": 0, "not_recorded": 0, "invalid": 0}
    references = 0
    resolvable = 0
    by_scheme: dict[str, int] = {}
    unprovenanced: list[dict[str, str]] = []
    unprovenanced_total = 0

    for record in records:
        raw = record.get(field, _MISSING)
        if raw is _MISSING or raw is None:
            state: PresenceState = "not_recorded"
        elif isinstance(raw, list):
            state = "present" if raw else "known_absent"
        elif isinstance(raw, str):
            state = "present" if raw.strip() else "known_absent"
        else:
            state = "invalid"

        counts[state] += 1
        if state == "present":
            values = raw if isinstance(raw, list) else [raw]
            if any(is_resolvable_reference(value) for value in values):
                resolvable += 1
            for value in values:
                references += 1
                for scheme in _reference_schemes(value):
                    by_scheme[scheme] = by_scheme.get(scheme, 0) + 1
        elif state in {"not_recorded", "known_absent"}:
            unprovenanced_total += 1
            if len(unprovenanced) < UNPROVENANCED_LIST_LIMIT:
                unprovenanced.append(
                    {
                        "id": str(record.get("id") or record.get("source") or "unknown"),
                        "state": state,
                    }
                )

    return {
        "records": len(records),
        **counts,
        "references": references,
        "resolvable": resolvable,
        "without_resolvable_identifier": len(records) - resolvable,
        "by_scheme": dict(sorted(by_scheme.items())),
        "unprovenanced": unprovenanced,
        "unprovenanced_truncated": unprovenanced_total > UNPROVENANCED_LIST_LIMIT,
    }


class _Missing:
    """Sentinel distinguishing an absent key from a JSON ``null``."""


_MISSING = _Missing()


def _safety_profile_state(disease: Disease) -> dict[str, Any]:
    """Measure the file-level provenance of ``adverse_events.json``.

    Safety profiles carry provenance at the file level (``source`` and
    ``limitations``), not per drug, so this is reported separately from the
    record-level provenance counts.
    """
    path = disease.data_dir / "adverse_events.json"
    if not path.is_file():
        return {"state": "not_recorded", "profiles": 0, "source": None, "limitations": 0}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, json.JSONDecodeError):
        return {"state": "invalid", "profiles": 0, "source": None, "limitations": 0}
    if not isinstance(payload, dict):
        return {"state": "invalid", "profiles": 0, "source": None, "limitations": 0}
    profiles = payload.get("profiles")
    profile_count = len(profiles) if isinstance(profiles, list) else 0
    limitations = payload.get("limitations")
    return {
        "state": "present" if profile_count else "known_absent",
        "profiles": profile_count,
        "source": payload.get("source") or None,
        "limitations": len(limitations) if isinstance(limitations, list) else 0,
    }


def _curation_state(disease: Disease) -> tuple[str, list[str]]:
    """Classify a module as generated, curated, or unknown.

    Delegates to :mod:`med_research.diseases.curation_state` so this report and
    the corpus browser always agree. ``unknown`` is a real answer: a module with
    no generator marker that is not CI-validated has no recorded provenance for
    how it was produced, and the report says so instead of guessing.
    """
    try:
        description = disease.profile.description or ""
    except (OSError, ValueError, TypeError):
        description = ""
    return classify_curation_state(disease.disease_id, disease.data_dir.parent, description)


def inspect_disease(disease_id: str) -> dict[str, Any]:
    """Measure one disease module's recorded evidence and provenance.

    Raises ``ValueError`` for an unregistered disease id; callers that scan a
    slice should use :func:`build_evidence_coverage_report`, which records the
    failure per disease instead of aborting the run.
    """
    disease = Disease(disease_id)
    checks = disease.validate()

    categories: dict[str, dict[str, Any]] = {}
    provenance_totals = {
        "evidence_records": 0,
        "present": 0,
        "known_absent": 0,
        "not_recorded": 0,
        "invalid": 0,
        "references": 0,
        "resolvable": 0,
    }
    by_scheme: dict[str, int] = {}
    unprovenanced: list[dict[str, str]] = []

    for category in _RECORD_CATEGORIES:
        state, records = _load_records(disease, category)
        entry: dict[str, Any] = {
            "label": category.label,
            "state": state,
            "records": len(records),
        }
        if category.provenance_field is None:
            entry["provenance"] = "not_applicable"
            entry["note"] = "This artifact's schema defines no citation field."
        elif state in {"present", "known_absent"}:
            summary = _provenance_summary(records, category.provenance_field)
            entry["provenance"] = summary
            # Relationships are excluded above, so every counted record is
            # evidence-bearing and belongs in the provenance denominator.
            provenance_totals["evidence_records"] += summary["records"]
            for key in ("present", "known_absent", "not_recorded", "invalid"):
                provenance_totals[key] += summary[key]
            provenance_totals["references"] += summary["references"]
            provenance_totals["resolvable"] += summary["resolvable"]
            for scheme, count in summary["by_scheme"].items():
                by_scheme[scheme] = by_scheme.get(scheme, 0) + count
            unprovenanced.extend(
                {"category": category.key, **item} for item in summary["unprovenanced"]
            )
        categories[category.key] = entry

    config = disease.config
    for config_category in _CONFIG_CATEGORIES:
        value = config.get(config_category.config_key)
        state = (
            "not_recorded" if config_category.config_key not in config else _presence_state(value)
        )
        config_records = 0
        if isinstance(value, list):
            config_records = len(value)
        elif isinstance(value, str):
            config_records = 1 if value.strip() else 0
        elif isinstance(value, dict):
            config_records = len(value)
        categories[config_category.key] = {
            "label": config_category.label,
            "state": state,
            "records": config_records,
            "origin": "config",
        }

    safety = _safety_profile_state(disease)
    categories["safety_profiles"] = {
        "label": "Adverse-event safety profiles",
        "state": safety["state"],
        "records": safety["profiles"],
        "file_provenance": {
            "source": safety["source"],
            "limitations": safety["limitations"],
        },
    }

    drug_count = len(disease.load_drugs().get("drugs") or [])
    strict_pass = all(status == "ok" for status in checks.values())
    readiness_tier = compute_tier(
        disease_id, checks, drug_count=drug_count, strict_pass=strict_pass
    )

    failures = [
        {"field": field, "status": status, "class": classify_failure(field, status)}
        for field, status in checks.items()
        if status != "ok"
    ]
    failure_classes: dict[str, int] = {}
    failure_groups: dict[str, int] = {}
    for failure in failures:
        failure_classes[failure["class"]] = failure_classes.get(failure["class"], 0) + 1
        failure_groups[failure["field"]] = failure_groups.get(failure["field"], 0) + 1

    state_counts: dict[str, int] = {"present": 0, "known_absent": 0, "not_recorded": 0}
    for entry in categories.values():
        state = entry["state"]
        if state in state_counts:
            state_counts[state] += 1

    limitations = list(_MEASUREMENT_LIMITATIONS)
    if not strict_pass:
        limitations.insert(
            0,
            "This module does not pass strict validation, so its coverage describes "
            "recorded inputs only and is not pipeline-ready.",
        )

    curation_state, generated_markers = _curation_state(disease)

    return {
        "disease_id": disease_id,
        "name": disease.profile.name,
        **tier_summary_row(disease_id, readiness_tier, strict_pass=strict_pass),
        "curation_state": curation_state,
        "generated_markers": generated_markers,
        "is_scaffold": curation_state == "generated",
        "categories": categories,
        "category_states": state_counts,
        "provenance": {
            **provenance_totals,
            "by_scheme": dict(sorted(by_scheme.items())),
            "without_provenance": provenance_totals["known_absent"]
            + provenance_totals["not_recorded"],
            "without_resolvable_identifier": provenance_totals["evidence_records"]
            - provenance_totals["resolvable"],
            "unprovenanced": unprovenanced[:UNPROVENANCED_LIST_LIMIT],
            "unprovenanced_truncated": len(unprovenanced) > UNPROVENANCED_LIST_LIMIT,
        },
        "evidence": summarize_evidence(
            provenance_totals["evidence_records"],
            provenance_totals["resolvable"],
            structurally_valid=strict_pass,
        ),
        "validation": {
            "passed": strict_pass,
            "failures": failures,
            "failure_classes": dict(sorted(failure_classes.items())),
            "failure_groups": dict(sorted(failure_groups.items(), key=lambda kv: (-kv[1], kv[0]))),
        },
        "limitations": limitations,
    }


def _stable_sample(ids: Sequence[str], *, sample_size: int, sample_seed: int) -> list[str]:
    """Return a version-stable sample ordered by a seeded content hash.

    ``random.sample`` is avoided because hash ordering of
    ``sha256(f"{seed}:{disease_id}")`` is reproducible across processes,
    platforms, and Python versions. The validation gate orders its sample the
    same way; the helper is repeated here so this report has no import-time
    dependency on a module that may not carry it.
    """
    if sample_size <= 0:
        return []
    ordered = sorted(
        ids,
        key=lambda disease_id: hashlib.sha256(f"{sample_seed}:{disease_id}".encode()).hexdigest(),
    )
    return ordered[:sample_size]


def _resolve_targets(
    *,
    disease_ids: Sequence[str] | None,
    tier_filter: str | None,
    limit: int | None,
    sample_size: int | None,
    sample_seed: int,
) -> tuple[list[str], str, int]:
    """Resolve the measured slice, its selection mode, and blocked exclusions."""
    if disease_ids is not None:
        selection = "explicit"
        candidates = [did for did in dict.fromkeys(disease_ids)]
    elif tier_filter:
        from med_research.diseases.validation_batch import _disease_ids_for_filter

        selection = "tier"
        candidates = list(_disease_ids_for_filter(cast(Any, tier_filter)))
    else:
        selection = "reference"
        candidates = list(DEFAULT_DISEASE_IDS)

    excluded_blocked = sum(1 for did in candidates if is_blocked_slug(did))
    candidates = [did for did in candidates if not is_blocked_slug(did)]

    if sample_size is not None:
        candidates = _stable_sample(candidates, sample_size=sample_size, sample_seed=sample_seed)
    if limit is not None:
        candidates = candidates[: max(limit, 0)]
    return candidates, selection, excluded_blocked


def build_evidence_coverage_report(
    *,
    disease_ids: Sequence[str] | None = None,
    tier_filter: str | None = None,
    limit: int | None = None,
    sample_size: int | None = None,
    sample_seed: int = 0,
) -> dict[str, Any]:
    """Build a deterministic evidence-coverage report over a bounded slice.

    Selection order is explicit ids, then tier filter, then the reference
    diseases. Blocked slugs are excluded and counted. Sampling is a seeded
    hash ordering, not ``random.sample``, so the same seed selects the same
    modules on every platform.
    """
    targets, selection, excluded_blocked = _resolve_targets(
        disease_ids=disease_ids,
        tier_filter=tier_filter,
        limit=limit,
        sample_size=sample_size,
        sample_seed=sample_seed,
    )

    population = len(Disease.list_all())

    per_disease: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for disease_id in targets:
        try:
            per_disease.append(inspect_disease(disease_id))
        except Exception as exc:  # noqa: BLE001 - reported, never swallowed
            errors.append({"disease_id": disease_id, "error": f"{type(exc).__name__}: {exc}"})

    measured = len(per_disease)
    tier_counts: dict[str, int] = {}
    measured_category_keys = [category.key for category in _RECORD_CATEGORIES] + [
        category.key for category in _CONFIG_CATEGORIES
    ]
    category_states: dict[str, dict[str, int]] = {
        key: {"present": 0, "known_absent": 0, "not_recorded": 0, "invalid": 0}
        for key in measured_category_keys
    }
    category_states["safety_profiles"] = {
        "present": 0,
        "known_absent": 0,
        "not_recorded": 0,
        "invalid": 0,
    }
    provenance = {
        "evidence_records": 0,
        "present": 0,
        "known_absent": 0,
        "not_recorded": 0,
        "invalid": 0,
        "references": 0,
        "resolvable": 0,
    }
    by_scheme: dict[str, int] = {}
    failure_classes: dict[str, int] = {}
    failure_groups: dict[str, int] = {}
    passed = 0
    evidenced_modules = 0
    scaffolds = 0
    curation_counts: dict[str, int] = {"generated": 0, "curated": 0, "unknown": 0}

    for row in per_disease:
        tier_counts[row["readiness_tier"]] = tier_counts.get(row["readiness_tier"], 0) + 1
        scaffolds += 1 if row["is_scaffold"] else 0
        curation_counts[row["curation_state"]] = curation_counts.get(row["curation_state"], 0) + 1
        passed += 1 if row["validation"]["passed"] else 0
        evidenced_modules += 1 if row["evidence"]["passes"] else 0
        for key, entry in row["categories"].items():
            state = entry["state"]
            bucket = category_states.setdefault(
                key, {"present": 0, "known_absent": 0, "not_recorded": 0, "invalid": 0}
            )
            if state in bucket:
                bucket[state] += 1
        for key in provenance:
            provenance[key] += row["provenance"][key]
        for scheme, count in row["provenance"]["by_scheme"].items():
            by_scheme[scheme] = by_scheme.get(scheme, 0) + count
        for key, count in row["validation"]["failure_classes"].items():
            failure_classes[key] = failure_classes.get(key, 0) + count
        for key, count in row["validation"]["failure_groups"].items():
            failure_groups[key] = failure_groups.get(key, 0) + count

    covers_full_population = (
        measured == population and selection in {"tier", "explicit"} and not sample_size
    )

    payload: dict[str, Any] = {
        "schema": REPORT_SCHEMA,
        "scope": {
            "selection": selection,
            "tier_filter": tier_filter,
            "requested": len(targets),
            "measured": measured,
            "errors": errors,
            "sample_size": sample_size,
            "sample_seed": sample_seed,
            "excluded_blocked": excluded_blocked,
            "population_modules": population,
            "population_basis": "Disease.list_all() over the checked-out module tree",
            "coverage_basis": (
                "full_population"
                if covers_full_population
                else ("sample" if sample_size else "bounded_unsampled_slice")
            ),
            "covers_full_population": covers_full_population,
        },
        "aggregate": {
            "diseases": measured,
            "scaffolds": scaffolds,
            "curation_states": dict(sorted(curation_counts.items())),
            "tier_counts": dict(sorted(tier_counts.items())),
            "category_states": {key: value for key, value in sorted(category_states.items())},
            "provenance": {
                **provenance,
                "by_scheme": dict(sorted(by_scheme.items())),
                "without_provenance": provenance["known_absent"] + provenance["not_recorded"],
                "without_resolvable_identifier": provenance["evidence_records"]
                - provenance["resolvable"],
            },
            "validation": {
                "passed": passed,
                "failed": measured - passed,
                "failure_classes": dict(sorted(failure_classes.items())),
                "failure_groups": dict(
                    sorted(failure_groups.items(), key=lambda kv: (-kv[1], kv[0]))
                ),
            },
            "evidence": {
                **summarize_evidence(
                    provenance["evidence_records"],
                    provenance["resolvable"],
                    structurally_valid=measured > 0 and passed == measured,
                ),
                "modules_passing": evidenced_modules,
                "modules_failing": measured - evidenced_modules,
                "gate_passes": measured > 0 and evidenced_modules == measured,
            },
        },
        "failure_class_definitions": FAILURE_CLASS_DEFINITIONS,
        "limitations": list(_MEASUREMENT_LIMITATIONS),
        "per_disease": per_disease,
    }
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return {
        **payload,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fingerprint": f"sha256:{fingerprint}",
    }


def render_summary(report: dict[str, Any]) -> str:
    """Render a compact researcher-facing summary of a coverage report."""
    scope = report["scope"]
    aggregate = report["aggregate"]
    provenance = aggregate["provenance"]
    total_records = provenance["evidence_records"]
    recorded = provenance["present"]

    lines = [
        "Evidence coverage summary",
        "========================",
        f"Selection: {scope['selection']}"
        + (f" (tier {scope['tier_filter']})" if scope.get("tier_filter") else ""),
        f"Measured: {scope['measured']} of {scope['population_modules']} registered modules"
        f" ({scope['coverage_basis']})",
    ]
    if not scope["covers_full_population"]:
        lines.append(
            "This is not a full-corpus measurement; do not read these counts as "
            "platform-wide rates."
        )
    if scope.get("excluded_blocked"):
        lines.append(f"Excluded non-disease slugs: {scope['excluded_blocked']}")
    if scope.get("errors"):
        lines.append(f"Modules that failed to load: {len(scope['errors'])}")
    if aggregate.get("curation_states"):
        states = ", ".join(f"{k}={v}" for k, v in aggregate["curation_states"].items())
        lines.append(f"Curation states: {states}")
    if aggregate.get("tier_counts"):
        tiers = ", ".join(f"{k}={v}" for k, v in aggregate["tier_counts"].items())
        lines.append(f"Readiness tiers: {tiers}")

    lines += [
        "",
        "Recorded provenance",
        "-------------------",
        f"Evidence-bearing records: {total_records}",
    ]
    if total_records:
        share = 100.0 * recorded / total_records
        resolvable = provenance.get("resolvable", 0)
        resolvable_share = 100.0 * resolvable / total_records
        lines.append(f"Records with a recorded citation: {recorded} ({share:.1f}%)")
        lines.append(
            f"Records with a resolvable identifier: {resolvable} ({resolvable_share:.1f}%)"
        )
    lines.append(f"Records explicitly empty: {provenance['known_absent']}")
    lines.append(f"Records with no citation field: {provenance['not_recorded']}")
    if provenance["invalid"]:
        lines.append(f"Unreadable provenance fields: {provenance['invalid']}")
    if provenance["by_scheme"]:
        schemes = ", ".join(f"{k}={v}" for k, v in provenance["by_scheme"].items())
        lines.append(f"Identifier schemes: {schemes}")

    lines += ["", "Validation", "----------"]
    validation = aggregate["validation"]
    lines.append(f"Passing strict validation: {validation['passed']}/{aggregate['diseases']}")
    evidence = aggregate.get("evidence") or {}
    if evidence.get("records"):
        lines.append(
            f"Evidenced modules (>= {evidence['target']:.0%} density): "
            f"{evidence['modules_passing']}/{aggregate['diseases']}"
        )
        lines.append(
            f"Evidence density: {evidence['density']:.1%} (target {evidence['target']:.0%})"
        )
    if validation["failure_classes"]:
        grouped = ", ".join(f"{k}={v}" for k, v in validation["failure_classes"].items())
        lines.append(f"Failure classes: {grouped}")

    weakest = sorted(
        report["per_disease"],
        key=lambda row: (
            row["provenance"]["evidence_records"] - row["provenance"]["present"],
            row["disease_id"],
        ),
        reverse=True,
    )[:5]
    if weakest and total_records:
        lines += ["", "Largest provenance gaps (by count)", "-------------------------------"]
        for row in weakest:
            gaps = row["provenance"]["without_provenance"]
            if not gaps:
                continue
            lines.append(
                f"{row['disease_id']}: {gaps} of {row['provenance']['evidence_records']} records"
            )

    lines += ["", "Limitations", "-----------"]
    for limitation in report["limitations"]:
        lines.append(f"- {limitation}")
    lines.append("")
    lines.append(f"Fingerprint: {report['fingerprint']}")
    return "\n".join(lines)


def write_evidence_coverage_report(
    report: dict[str, Any],
    path: Path | None = None,
) -> Path:
    """Persist a coverage report as canonical JSON."""
    root = Path(__file__).resolve().parents[3]
    out = path or (root / "data" / "reports" / "evidence_coverage_report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


__all__ = [
    "DEFAULT_DISEASE_IDS",
    "EVIDENCE_DENSITY_TARGET",
    "FAILURE_CLASS_DEFINITIONS",
    "GENERATOR_MARKER",
    "KNOWN_REFERENCE_SCHEMES",
    "REPORT_SCHEMA",
    "SCAFFOLD_MARKER",
    "build_evidence_coverage_report",
    "inspect_disease",
    "render_summary",
    "write_evidence_coverage_report",
]
