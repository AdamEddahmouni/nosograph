"""Tests for corpus status reporting."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from med_research.diseases import corpus_status
from med_research.diseases.corpus_status import build_corpus_status


def test_build_corpus_status_limit() -> None:
    report = build_corpus_status(limit=3, include_symptom_source=False)
    assert report["aggregate"]["total"] == 3
    assert len(report["per_disease"]) == 3


@pytest.mark.parametrize(
    ("symptoms", "registry_entry", "availability", "source_labels", "expected"),
    [
        (["fatigue"], None, {}, {}, "populated"),
        (
            [],
            {"mondo_id": "MONDO:1"},
            {"biomed_hpoa": True},
            {"biomed_hpoa": ["Fatigue"]},
            "awaiting_curation",
        ),
        (
            [],
            {"efo_id": "EFO_1"},
            {"ot_phenotype": True},
            {"ot_phenotype": []},
            "no_source_annotations",
        ),
        (
            [],
            {"efo_id": "EFO_1"},
            {"ot_phenotype": False, "biomed_hpoa": False},
            {},
            "source_unavailable",
        ),
        ([], {}, {"ot_phenotype": True}, {}, "identifier_unresolved"),
    ],
)
def test_symptom_coverage_classification(
    symptoms: list[str],
    registry_entry: dict[str, Any] | None,
    availability: dict[str, bool],
    source_labels: dict[str, list[str]],
    expected: str,
) -> None:
    assert (
        corpus_status._symptom_coverage_state(symptoms, registry_entry, availability, source_labels)
        == expected
    )


def test_build_corpus_status_reports_symptom_coverage_without_changing_legacy_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    diseases = {
        "populated": {"SYMPTOMS": ["Rash"]},
        "awaiting": {"SYMPTOMS": []},
        "no_annotations": {"SYMPTOMS": []},
        "unavailable": {"SYMPTOMS": []},
        "unresolved": {"SYMPTOMS": []},
        "mondo_only_ot": {"SYMPTOMS": []},
        "query_failed": {"SYMPTOMS": []},
        "mixed_query_failure": {"SYMPTOMS": []},
        "broken": {"SYMPTOMS": []},
    }
    registry = {
        "populated": {},
        "awaiting": {"mondo_id": "MONDO:1"},
        "no_annotations": {"mondo_id": "MONDO:2"},
        "unavailable": {"efo_id": "EFO_2"},
        "unresolved": {},
        "mondo_only_ot": {"mondo_id": "MONDO:3"},
        "query_failed": {"efo_id": "EFO_3"},
        "mixed_query_failure": {"mondo_id": "MONDO:4", "efo_id": "EFO_4"},
        "broken": {},
    }

    class FakeDisease:
        @staticmethod
        def list_all() -> list[str]:
            return list(diseases)

        def __init__(self, disease_id: str) -> None:
            if disease_id == "broken":
                raise ValueError("broken module")
            self.config = diseases[disease_id]
            self.profile = SimpleNamespace(name=disease_id)

        def validate(self) -> dict[str, str]:
            return {}

    class FakeStore:
        def get_phenotypes(
            self, disease_id: str, limit: int = 1, *, raise_on_error: bool = False
        ) -> list[str]:
            assert limit == 1
            assert raise_on_error
            if disease_id in {"EFO_3", "EFO_4"}:
                raise RuntimeError("local parquet unavailable")
            return []

    monkeypatch.setattr(corpus_status, "Disease", FakeDisease)
    monkeypatch.setattr(
        corpus_status,
        "_entity_counts",
        lambda _disease_id: {"genes": 0, "drugs": 0, "pathways": 0},
    )
    monkeypatch.setattr(
        corpus_status,
        "load_disease_registry",
        lambda: [{"id": disease_id, **entry} for disease_id, entry in registry.items()],
    )

    class QueryFailingStore(FakeStore):
        def get_phenotypes(
            self, disease_id: str, limit: int = 1, *, raise_on_error: bool = False
        ) -> list[str]:
            if disease_id in {"EFO_3", "EFO_4"}:
                raise RuntimeError("local parquet unavailable")
            return super().get_phenotypes(disease_id, limit=limit, raise_on_error=raise_on_error)

    monkeypatch.setattr(corpus_status, "OpenTargetsBulkStore", QueryFailingStore)
    from med_research.diseases import scaffold

    def forbidden_side_effect(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("corpus status must not write files or make HTTP requests")

    monkeypatch.setattr(scaffold, "_http_post_json", forbidden_side_effect)
    monkeypatch.setattr(Path, "write_text", forbidden_side_effect)
    availability_calls = 0

    def available_sources(_store: Any) -> dict[str, bool]:
        nonlocal availability_calls
        availability_calls += 1
        return {"biomed_hpoa": True, "ot_phenotype": True}

    monkeypatch.setattr(corpus_status, "local_symptom_source_availability", available_sources)
    monkeypatch.setattr(
        corpus_status,
        "_hpo_symptoms_from_biomed",
        lambda mondo_id, limit=1, raise_on_error=False: (
            ["Fatigue"] if mondo_id == "MONDO:1" else []
        ),
    )

    report = build_corpus_status(limit=None, include_symptom_source=True)

    rows = {row["disease_id"]: row for row in report["per_disease"]}
    assert availability_calls == 1
    assert rows["populated"]["symptom_coverage"] == "populated"
    assert rows["populated"]["symptom_count"] == 1
    assert rows["populated"]["symptom_source"] == "config"
    assert rows["awaiting"]["symptom_coverage"] == "awaiting_curation"
    assert rows["awaiting"]["symptom_count"] == 0
    assert rows["awaiting"]["symptom_source"] == "none"
    assert rows["no_annotations"]["symptom_coverage"] == "no_source_annotations"
    assert rows["unavailable"]["symptom_coverage"] == "no_source_annotations"
    assert rows["query_failed"]["symptom_coverage"] == "source_unavailable"
    assert rows["mixed_query_failure"]["symptom_coverage"] == "no_source_annotations"
    assert rows["unresolved"]["symptom_coverage"] == "identifier_unresolved"
    assert rows["mondo_only_ot"]["symptom_coverage"] == "no_source_annotations"
    assert rows["broken"]["tier"] == "blocked"
    assert "symptom_coverage" not in rows["broken"]
    assert report["aggregate"]["symptoms_populated"] == 1
    assert report["aggregate"]["symptom_coverage"] == {
        "populated": 1,
        "awaiting_curation": 1,
        "no_source_annotations": 4,
        "source_unavailable": 1,
        "identifier_unresolved": 1,
    }


def test_build_corpus_status_omits_legacy_source_when_not_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeDisease:
        @staticmethod
        def list_all() -> list[str]:
            return ["example"]

        def __init__(self, _disease_id: str) -> None:
            self.config = {"SYMPTOMS": []}
            self.profile = SimpleNamespace(name="Example")

        def validate(self) -> dict[str, str]:
            return {}

    monkeypatch.setattr(corpus_status, "Disease", FakeDisease)
    monkeypatch.setattr(
        corpus_status,
        "_entity_counts",
        lambda _disease_id: {"genes": 0, "drugs": 0, "pathways": 0},
    )
    monkeypatch.setattr(corpus_status, "load_disease_registry", lambda: [{"id": "example"}])
    monkeypatch.setattr(
        corpus_status,
        "local_symptom_source_availability",
        lambda _store: {"biomed_hpoa": False, "ot_phenotype": False},
    )
    monkeypatch.setattr(corpus_status, "_hpo_symptoms_from_biomed", lambda *_args, **_kwargs: [])

    report = build_corpus_status(include_symptom_source=False)

    assert "symptom_source" not in report["per_disease"][0]
    assert report["aggregate"]["symptom_coverage"]["identifier_unresolved"] == 1
