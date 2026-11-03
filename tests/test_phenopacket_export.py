"""Tests for the experimental disease-level phenotype evidence export.

These tests are offline and read only synthetic fixtures from
``tests/fixtures/phenopacket``. They assert the two properties that make the
export trustworthy: deterministic bytes, and explicit honest missingness.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from med_research.biomed.models import EvidenceDirection
from med_research.biomed.phenopacket import (
    NOT_RECORDED,
    PHENOPACKET_ALIGNMENT,
    PhenopacketExportError,
    PhenotypeEvidenceBundleInput,
    build_bundle,
    dumps_bundle,
    export_bundle,
    write_bundle,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "phenopacket"

#: Keys that would make the payload look like an observation of a real person.
FORBIDDEN_OBSERVATION_KEYS = frozenset(
    {
        "subject",
        "individual",
        "demographics",
        "sex",
        "gender",
        "age",
        "ageAtOnset",
        "ageAtLastEncounter",
        "biosamples",
        "measurements",
        "variants",
        "pedigree",
        "diseases",
        "medicalActions",
        "interpretations",
    }
)


def _load(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _walk_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            keys.add(key)
            keys |= _walk_keys(nested)
    elif isinstance(value, list):
        for item in value:
            keys |= _walk_keys(item)
    return keys


def test_valid_fixture_export_is_byte_identical_across_calls() -> None:
    payload = _load("valid_input.json")

    first = export_bundle(payload)
    second = export_bundle(payload)

    assert first == second
    assert first.endswith("\n")
    # Canonical form: compact separators, so no pretty-printed indentation.
    assert '\n  "' not in first
    assert ', "' not in first


def test_dump_is_canonical_sorted_json() -> None:
    text = export_bundle(_load("valid_input.json"))
    payload = json.loads(text)

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert text == canonical + "\n"


def test_features_are_ordered_by_hpo_id() -> None:
    bundle = build_bundle(_load("valid_input.json"))
    ids = [feature.hpo_id for feature in bundle.phenotypic_features]

    assert ids == ["HP:0000001", "HP:0000002", "HP:0000003"]


def test_provenance_is_sorted_and_complete() -> None:
    bundle = build_bundle(_load("valid_input.json"))
    first = bundle.phenotypic_features[0]

    assert first.hpo_id == "HP:0000001"
    assert [ref.source_id for ref in first.provenance] == [
        "synthetic-hpoa",
        "synthetic-literature",
    ]
    assert bundle.provenance_summary.source_ids == [
        "synthetic-hpoa",
        "synthetic-literature",
    ]
    assert bundle.provenance_summary.annotated_feature_count == 3


def test_missing_values_are_recorded_not_dropped_and_not_zeroed() -> None:
    bundle = build_bundle(_load("valid_input.json"))
    contradicted = next(
        feature for feature in bundle.phenotypic_features if feature.hpo_id == "HP:0000003"
    )

    assert contradicted.hpo_label == NOT_RECORDED
    assert contradicted.frequency == NOT_RECORDED
    assert contradicted.direction is EvidenceDirection.CONTRADICTORY
    assert contradicted.provenance[0].version == NOT_RECORDED
    assert contradicted.provenance[0].checksum == NOT_RECORDED
    # The missing values are listed explicitly rather than only being absent.
    assert "phenotypicFeatures[HP:0000003].hpo_label" in bundle.missing_fields
    assert "phenotypicFeatures[HP:0000003].frequency" in bundle.missing_fields
    assert bundle.missing_fields == sorted(bundle.missing_fields)


def test_contradictory_evidence_is_not_translated_into_exclusion() -> None:
    bundle = build_bundle(_load("valid_input.json"))
    serialized = json.loads(dumps_bundle(bundle))

    feature = next(
        item for item in serialized["phenotypic_features"] if item["hpo_id"] == "HP:0000003"
    )
    assert feature["direction"] == "contradictory"
    assert "excluded" not in feature
    assert any("not translated" in warning for warning in bundle.warnings)


def test_bundle_states_its_alignment_and_disclaimer() -> None:
    bundle = build_bundle(_load("valid_input.json"))

    assert bundle.phenopacket_alignment == PHENOPACKET_ALIGNMENT
    assert "not a conformant Phenopacket" in bundle.phenopacket_alignment
    assert bundle.export_scope.value == "disease_evidence"
    assert "Not a patient Phenopacket" in bundle.disclaimer


def test_export_never_contains_patient_observation_keys() -> None:
    serialized = json.loads(export_bundle(_load("valid_input.json")))

    assert _walk_keys(serialized) & FORBIDDEN_OBSERVATION_KEYS == set()

    # Guard the constant itself so a future edit cannot silently empty it.
    assert "subject" in FORBIDDEN_OBSERVATION_KEYS
    assert "biosamples" in FORBIDDEN_OBSERVATION_KEYS


def test_rejects_fixture_without_provenance() -> None:
    with pytest.raises(PhenopacketExportError) as excinfo:
        build_bundle(_load("invalid_missing_provenance.json"))

    assert any("sources requires at least one" in message for message in excinfo.value.messages)


def test_rejects_malformed_disease_curie() -> None:
    with pytest.raises(PhenopacketExportError) as excinfo:
        build_bundle({"disease_curie": "not-a-curie"})

    assert any("is not a valid CURIE" in message for message in excinfo.value.messages)


@pytest.mark.parametrize("hpo_id", ["HP:0001", "0001250", "MONDO:0007915", "HP:000000x"])
def test_rejects_non_hpo_term_ids(hpo_id: str) -> None:
    payload = {
        "disease_curie": "MONDO:0000001",
        "phenotypes": [
            {
                "hpo_id": hpo_id,
                "direction": "supporting",
                "sources": [{"source_id": "synthetic"}],
            }
        ],
    }

    with pytest.raises(PhenopacketExportError) as excinfo:
        build_bundle(payload)

    assert excinfo.value.messages


def test_rejects_missing_direction() -> None:
    payload = {
        "disease_curie": "MONDO:0000001",
        "phenotypes": [
            {
                "hpo_id": "HP:0000001",
                "sources": [{"source_id": "synthetic"}],
            }
        ],
    }

    with pytest.raises(PhenopacketExportError) as excinfo:
        build_bundle(payload)

    assert any(".direction is required" in message for message in excinfo.value.messages)


def test_collects_every_problem_in_one_pass() -> None:
    payload = {
        "disease_curie": "",
        "phenotypes": [
            {"hpo_id": "HP:0001", "direction": "maybe", "sources": []},
            {"hpo_id": "HP:0000002", "sources": [{"source_id": ""}]},
        ],
    }

    with pytest.raises(PhenopacketExportError) as excinfo:
        build_bundle(payload)

    messages = "\n".join(excinfo.value.messages)
    assert "disease_curie is required" in messages
    assert "phenotypes[0].hpo_id" in messages
    assert "phenotypes[0].direction" in messages
    assert "phenotypes[0].sources" in messages
    assert "phenotypes[1].direction is required" in messages
    assert "phenotypes[1].sources[0].source_id is required" in messages


def test_rejects_unknown_fields() -> None:
    payload = {
        "disease_curie": "MONDO:0000001",
        "phenotypes": [],
        "submitted_by": "someone",
    }

    with pytest.raises(PhenopacketExportError) as excinfo:
        build_bundle(payload)

    assert any("unknown top-level field" in message for message in excinfo.value.messages)


def test_duplicate_annotations_are_collapsed_with_a_warning() -> None:
    phenotype = {
        "hpo_id": "HP:0000001",
        "direction": "supporting",
        "sources": [{"source_id": "synthetic"}],
    }
    bundle = build_bundle(
        {
            "disease_curie": "MONDO:0000001",
            "phenotypes": [phenotype, dict(phenotype)],
        }
    )

    assert len(bundle.phenotypic_features) == 1
    assert any("collapsed" in warning for warning in bundle.warnings)


def test_empty_phenotypes_is_explicit_never_absence() -> None:
    bundle = build_bundle({"disease_curie": "MONDO:0000001"})

    assert bundle.phenotypic_features == []
    assert "phenotypicFeatures" in bundle.missing_fields
    assert "disease.label" in bundle.missing_fields
    assert any("rather than inferring absence" in warning for warning in bundle.warnings)


def test_non_mondo_disease_curie_is_a_warning_not_a_silent_rewrite() -> None:
    bundle = build_bundle({"disease_curie": "EFO:0001370"})

    assert bundle.disease.curie == "EFO:0001370"
    assert any("not a MONDO CURIE" in warning for warning in bundle.warnings)


def test_curie_is_normalized_for_round_trip_stability() -> None:
    bundle = build_bundle(
        {
            "disease_curie": " mondo:0000001 ",
            "phenotypes": [
                {
                    "hpo_id": "hp:0000001",
                    "direction": "supporting",
                    "sources": [{"source_id": "synthetic"}],
                }
            ],
        }
    )

    assert bundle.disease.curie == "MONDO:0000001"
    assert bundle.phenotypic_features[0].hpo_id == "HP:0000001"


def test_input_model_is_accepted_directly() -> None:
    payload = PhenotypeEvidenceBundleInput.model_validate(_load("valid_input.json"))
    from_model = export_bundle(payload)
    from_mapping = export_bundle(_load("valid_input.json"))

    assert from_model == from_mapping


def test_write_bundle_creates_parents_and_uses_lf(tmp_path: Path) -> None:
    bundle = build_bundle(_load("valid_input.json"))
    target = tmp_path / "nested" / "bundle.json"

    written = write_bundle(target, bundle)

    assert written == target
    raw = target.read_bytes()
    assert b"\r\n" not in raw
    assert raw.decode("utf-8") == dumps_bundle(bundle)


def test_export_bundle_writes_the_same_bytes_it_returns(tmp_path: Path) -> None:
    target = tmp_path / "bundle.json"

    text = export_bundle(_load("valid_input.json"), path=target)

    assert target.read_text(encoding="utf-8") == text


def test_payload_type_error_is_explicit() -> None:
    with pytest.raises(TypeError, match="payload must be a mapping"):
        build_bundle(["not", "a", "mapping"])  # type: ignore[arg-type]
