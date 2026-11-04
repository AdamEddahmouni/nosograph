"""Build and serialize the experimental disease-level phenotype evidence bundle.

The entry points are :func:`build_bundle`, :func:`dumps_bundle` and
:func:`write_bundle`. They never reach the network and never read the
biomedical store: the caller supplies the evidence, and this module validates
and serializes it.

Example::

    from med_research.biomed.phenopacket import build_bundle, dumps_bundle

    bundle = build_bundle(payload)
    print(dumps_bundle(bundle))

Identical payloads produce byte-identical output.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from med_research.biomed.errors import BiomedicalError
from med_research.biomed.identifiers import normalize_curie
from med_research.biomed.models import EvidenceDirection
from med_research.biomed.phenopacket.models import (
    DISCLAIMER,
    NOT_RECORDED,
    DiseaseReference,
    EvidenceSourceRef,
    PhenotypeAnnotation,
    PhenotypeEvidenceBundle,
    PhenotypeEvidenceBundleInput,
    PhenotypeEvidenceInput,
    ProvenanceSummary,
)

_HPO_ID_PATTERN = re.compile(r"^HP:\d{7}$")
_VALID_DIRECTIONS = tuple(sorted(direction.value for direction in EvidenceDirection))
_MONDO_PREFIX = "MONDO"
_SOURCE_MISSING_FIELDS = ("source_record_id", "version", "checksum", "attribution")
_TOP_LEVEL_KEYS = frozenset({"disease_curie", "disease_label", "phenotypes"})
_PHENOTYPE_KEYS = frozenset({"hpo_id", "hpo_label", "direction", "frequency", "notes", "sources"})
_SOURCE_KEYS = frozenset(
    {
        "source_id",
        "source_record_id",
        "source_url",
        "version",
        "checksum",
        "attribution",
    }
)


class PhenopacketExportError(BiomedicalError):
    """Raised when a phenotype evidence bundle cannot be built.

    ``messages`` holds every problem found in one pass, so a caller can fix the
    whole payload instead of one field at a time.
    """

    def __init__(self, messages: list[str]) -> None:
        self.messages = list(messages)
        super().__init__("invalid phenotype evidence export input: " + "; ".join(self.messages))


def _as_mapping(payload: Mapping[str, Any] | BaseModel) -> dict[str, Any]:
    if isinstance(payload, BaseModel):
        return payload.model_dump()
    if not isinstance(payload, Mapping):
        raise TypeError(
            "payload must be a mapping or a PhenotypeEvidenceBundleInput, "
            f"got {type(payload).__name__}"
        )
    return dict(payload)


def _text_or_not_recorded(value: object) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return NOT_RECORDED


def _optional_text(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _normalized_curie(value: str, field: str, errors: list[str]) -> str:
    try:
        return normalize_curie(value)
    except ValueError:
        errors.append(f"{field} {value!r} is not a valid CURIE")
        return ""


def _check_unknown_keys(
    payload: Mapping[str, Any],
    allowed: frozenset[str],
    prefix: str,
    errors: list[str],
) -> None:
    unknown = sorted(set(payload) - allowed)
    if unknown:
        errors.append(f"{prefix} has unknown field(s): {', '.join(unknown)}")


def _collect_errors(raw: Mapping[str, Any]) -> list[str]:
    """Collect every problem in ``raw`` in one pass instead of raising early."""

    errors: list[str] = []

    unknown = sorted(set(raw) - _TOP_LEVEL_KEYS)
    if unknown:
        errors.append(f"unknown top-level field(s): {', '.join(unknown)}")

    disease_curie = raw.get("disease_curie")
    if not isinstance(disease_curie, str) or not disease_curie.strip():
        errors.append("disease_curie is required and must be a non-empty CURIE string")
    else:
        _normalized_curie(disease_curie, "disease_curie", errors)

    disease_label = raw.get("disease_label")
    if disease_label is not None and not isinstance(disease_label, str):
        errors.append("disease_label must be a string when provided")

    phenotypes = raw.get("phenotypes", [])
    if phenotypes is None:
        phenotypes = []
    if not isinstance(phenotypes, (list, tuple)):
        errors.append("phenotypes must be a list")
        return errors

    for index, item in enumerate(phenotypes):
        prefix = f"phenotypes[{index}]"
        if not isinstance(item, Mapping):
            errors.append(f"{prefix} must be an object")
            continue
        _check_unknown_keys(item, _PHENOTYPE_KEYS, prefix, errors)

        hpo_id = item.get("hpo_id")
        if not isinstance(hpo_id, str) or not hpo_id.strip():
            errors.append(f"{prefix}.hpo_id is required")
        else:
            normalized_hpo = _normalized_curie(hpo_id, f"{prefix}.hpo_id", errors)
            if normalized_hpo and not _HPO_ID_PATTERN.fullmatch(normalized_hpo):
                errors.append(
                    f"{prefix}.hpo_id {hpo_id!r} must be an HPO term id of the form 'HP:0000000'"
                )

        direction = item.get("direction")
        if direction is None:
            errors.append(
                f"{prefix}.direction is required (one of: {', '.join(_VALID_DIRECTIONS)})"
            )
        elif isinstance(direction, EvidenceDirection):
            pass
        elif not isinstance(direction, str) or direction not in _VALID_DIRECTIONS:
            errors.append(
                f"{prefix}.direction {direction!r} must be one of: {', '.join(_VALID_DIRECTIONS)}"
            )

        sources = item.get("sources")
        if not isinstance(sources, (list, tuple)) or not sources:
            errors.append(f"{prefix}.sources requires at least one provenance source reference")
            continue
        for source_index, source in enumerate(sources):
            source_prefix = f"{prefix}.sources[{source_index}]"
            if not isinstance(source, Mapping):
                errors.append(f"{source_prefix} must be an object")
                continue
            _check_unknown_keys(source, _SOURCE_KEYS, source_prefix, errors)
            source_id = source.get("source_id")
            if not isinstance(source_id, str) or not source_id.strip():
                errors.append(f"{source_prefix}.source_id is required")

    return errors


def _source_ref(source: Mapping[str, Any]) -> EvidenceSourceRef:
    return EvidenceSourceRef(
        source_id=str(source["source_id"]).strip(),
        source_record_id=_text_or_not_recorded(source.get("source_record_id")),
        source_url=_optional_text(source.get("source_url")),
        version=_text_or_not_recorded(source.get("version")),
        checksum=_text_or_not_recorded(source.get("checksum")),
        attribution=_text_or_not_recorded(source.get("attribution")),
    )


def _annotation(item: Mapping[str, Any]) -> PhenotypeAnnotation:
    provenance = sorted(
        (_source_ref(source) for source in item["sources"]),
        key=lambda ref: (
            ref.source_id,
            ref.source_record_id,
            ref.version,
            ref.checksum,
        ),
    )
    return PhenotypeAnnotation(
        hpo_id=normalize_curie(str(item["hpo_id"])),
        hpo_label=_text_or_not_recorded(item.get("hpo_label")),
        direction=EvidenceDirection(item["direction"]),
        frequency=_text_or_not_recorded(item.get("frequency")),
        provenance=provenance,
        notes=_optional_text(item.get("notes")),
    )


def _feature_sort_key(feature: PhenotypeAnnotation) -> tuple[str, str, tuple[str, ...]]:
    return (
        feature.hpo_id,
        feature.direction.value,
        tuple(ref.source_id for ref in feature.provenance),
    )


def _missing_fields(disease_label: str, features: list[PhenotypeAnnotation]) -> list[str]:
    missing: set[str] = set()
    if disease_label == NOT_RECORDED:
        missing.add("disease.label")
    if not features:
        missing.add("phenotypicFeatures")
    for feature in features:
        if feature.hpo_label == NOT_RECORDED:
            missing.add(f"phenotypicFeatures[{feature.hpo_id}].hpo_label")
        if feature.frequency == NOT_RECORDED:
            missing.add(f"phenotypicFeatures[{feature.hpo_id}].frequency")
        for ref in feature.provenance:
            for field_name in _SOURCE_MISSING_FIELDS:
                if getattr(ref, field_name) == NOT_RECORDED:
                    missing.add(
                        f"phenotypicFeatures[{feature.hpo_id}]"
                        f".provenance[{ref.source_id}].{field_name}"
                    )
    return sorted(missing)


def _warnings(disease_curie: str, features: list[PhenotypeAnnotation], collapsed: int) -> list[str]:
    warnings: list[str] = []
    if collapsed:
        warnings.append(
            f"{collapsed} duplicate phenotype annotation(s) were collapsed; "
            "duplicates with identical evidence carry no extra information."
        )
    if not disease_curie.startswith(f"{_MONDO_PREFIX}:"):
        warnings.append(
            f"disease identifier {disease_curie} is not a MONDO CURIE; "
            "NosoGraph aligns disease knowledge to MONDO where a term exists."
        )
    contradicted = sorted(
        {
            feature.hpo_id
            for feature in features
            if feature.direction is EvidenceDirection.CONTRADICTORY
        }
    )
    if contradicted:
        warnings.append(
            "contradictory evidence is recorded for "
            + ", ".join(contradicted)
            + "; evidence direction is carried verbatim and is not translated "
            "into an 'excluded' phenotype assertion."
        )
    if not features:
        warnings.append(
            "no phenotype annotations were supplied; the bundle records an "
            "empty phenotypicFeatures list rather than inferring absence."
        )
    return warnings


def build_bundle(
    payload: Mapping[str, Any] | PhenotypeEvidenceBundleInput | PhenotypeEvidenceInput,
) -> PhenotypeEvidenceBundle:
    """Validate ``payload`` and return a deterministic evidence bundle.

    Raises:
        PhenopacketExportError: when the payload has one or more problems. All
            problems are reported together.
        TypeError: when ``payload`` is neither a mapping nor a pydantic model.
    """

    raw = _as_mapping(payload)
    errors = _collect_errors(raw)
    if errors:
        raise PhenopacketExportError(errors)

    disease_curie = normalize_curie(str(raw["disease_curie"]))
    disease_label = _text_or_not_recorded(raw.get("disease_label"))

    annotations = [_annotation(item) for item in raw.get("phenotypes") or []]
    ordered = sorted(annotations, key=_feature_sort_key)
    features: list[PhenotypeAnnotation] = []
    for feature in ordered:
        if features and features[-1] == feature:
            continue
        features.append(feature)

    source_ids = sorted({ref.source_id for feature in features for ref in feature.provenance})

    return PhenotypeEvidenceBundle(
        disease=DiseaseReference(curie=disease_curie, label=disease_label),
        phenotypic_features=features,
        provenance_summary=ProvenanceSummary(
            source_count=len(source_ids),
            source_ids=source_ids,
            annotated_feature_count=len(features),
        ),
        missing_fields=_missing_fields(disease_label, features),
        warnings=_warnings(disease_curie, features, len(ordered) - len(features)),
        disclaimer=DISCLAIMER,
    )


def dumps_bundle(bundle: PhenotypeEvidenceBundle) -> str:
    """Serialize ``bundle`` to canonical JSON with a trailing newline.

    Keys are sorted, separators are explicit, and no timestamp is embedded, so
    two identical payloads serialize to byte-identical text.
    """

    text = json.dumps(
        bundle.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return text + "\n"


def write_bundle(path: str | Path, bundle: PhenotypeEvidenceBundle) -> Path:
    """Write ``bundle`` to ``path`` as UTF-8 with LF endings; return the path."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(dumps_bundle(bundle), encoding="utf-8", newline="\n")
    return target


def export_bundle(
    payload: Mapping[str, Any] | PhenotypeEvidenceBundleInput | PhenotypeEvidenceInput,
    *,
    path: str | Path | None = None,
) -> str:
    """Build ``payload``, optionally write it, and return the canonical JSON."""

    bundle = build_bundle(payload)
    text = dumps_bundle(bundle)
    if path is not None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
    return text


__all__ = [
    "PhenopacketExportError",
    "build_bundle",
    "dumps_bundle",
    "export_bundle",
    "write_bundle",
]
