"""Tests for the evidence-coverage and provenance inspection workflow.

Every case runs against an in-memory fake ``Disease`` whose ``data_dir`` points
at ``tmp_path``. No real disease module is read, created, or modified, and no
network access is involved, so the suite is deterministic and safe under
``pytest-xdist``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import med_research.diseases.evidence_coverage as evidence_coverage
from med_research.diseases.evidence_coverage import (
    REPORT_SCHEMA,
    _reference_schemes,
    build_evidence_coverage_report,
    inspect_disease,
    render_summary,
    write_evidence_coverage_report,
)

pytestmark = pytest.mark.unit


class _FakeProfile:
    """Minimal stand-in for ``DiseaseProfile``."""

    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description


def _passing_checks() -> dict[str, str]:
    """Every field strict validation inspects, all passing."""
    return {
        "genes": "ok",
        "drugs": "ok",
        "pathways": "ok",
        "relationships": "ok",
        "profile": "ok",
        "SYMPTOMS": "ok",
        "PUBMED_QUERIES": "ok",
        "TRIAL_QUERY": "ok",
        "GWAS_SEARCH_TERMS": "ok",
        "CAR_T_SCORES": "ok",
        "DRUG_SAFETY_RISK": "ok",
    }


def _full_config() -> dict[str, Any]:
    return {
        "SYMPTOMS": ["fever"],
        "PUBMED_QUERIES": ["lupus review"],
        "TRIAL_QUERY": "lupus",
        "GWAS_SEARCH_TERMS": ["lupus"],
        "DISEASE_SPECIFIC_RISK": {"belimumab": 1},
    }


def _install(
    monkeypatch: pytest.MonkeyPatch,
    modules: dict[str, dict[str, Any]],
    *,
    population: list[str] | None = None,
) -> type:
    """Install a fake ``Disease`` that resolves ids from ``modules``.

    ``population`` controls what ``Disease.list_all()`` reports and defaults to
    the module ids, so a test can model a large registry measured through a
    small slice.
    """
    population_ids = sorted(population if population is not None else modules)

    class _FakeDisease:
        def __init__(self, disease_id: str) -> None:
            spec = modules[disease_id]
            self.disease_id = disease_id
            self.data_dir: Path = spec["root"]
            self.profile = spec.get("profile") or _FakeProfile(disease_id)
            self.config: dict[str, Any] = spec.get("config", {})
            self._checks = spec.get("checks", _passing_checks())
            self._fail = spec.get("fail", False)

        @staticmethod
        def list_all() -> list[str]:
            return list(population_ids)

        def validate(self) -> dict[str, str]:
            if self._fail:
                raise RuntimeError("validator exploded")
            return dict(self._checks)

        def _load(self, filename: str, collection: str) -> dict[str, Any]:
            path = self.data_dir / filename
            if not path.is_file():
                # The real loader raises; the fake returns an empty collection so
                # drug_count lookups do not mask the behaviour under test.
                return {collection: []}
            return json.loads(path.read_text(encoding="utf-8-sig"))

        def load_genes(self) -> dict[str, Any]:
            return self._load("genes.json", "genes")

        def load_drugs(self) -> dict[str, Any]:
            return self._load("drugs.json", "drugs")

        def load_pathways(self) -> dict[str, Any]:
            return self._load("pathways.json", "pathways")

        def load_relationships(self) -> dict[str, Any]:
            return self._load("relationships.json", "relationships")

    monkeypatch.setattr(evidence_coverage, "Disease", _FakeDisease)
    return _FakeDisease


def _module(tmp_path: Path, name: str) -> Path:
    root = tmp_path / name
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write(root: Path, filename: str, payload: Any) -> None:
    (root / filename).write_text(json.dumps(payload), encoding="utf-8")


# ── Record-level provenance: present / known_absent / not_recorded ──────────


def test_provenance_three_states_are_counted_separately(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _module(tmp_path, "alpha")
    _write(
        root,
        "genes.json",
        {
            "genes": [
                {"id": "G1", "references": ["PMID:111"]},
                {"id": "G2", "references": []},
                {"id": "G3"},
            ]
        },
    )
    _install(monkeypatch, {"alpha": {"root": root}})

    row = inspect_disease("alpha")
    provenance = row["provenance"]

    assert provenance["evidence_records"] == 3
    assert provenance["present"] == 1
    assert provenance["known_absent"] == 1
    assert provenance["not_recorded"] == 1
    assert provenance["without_provenance"] == 2
    assert provenance["without_provenance"] == (
        provenance["known_absent"] + provenance["not_recorded"]
    )
    states = {item["id"]: item["state"] for item in provenance["unprovenanced"]}
    assert states == {"G2": "known_absent", "G3": "not_recorded"}


def test_empty_collection_is_known_absent_not_present(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _module(tmp_path, "alpha")
    _write(root, "genes.json", {"genes": []})
    _install(monkeypatch, {"alpha": {"root": root}})

    row = inspect_disease("alpha")
    assert row["categories"]["genetics"]["state"] == "known_absent"
    assert row["categories"]["genetics"]["records"] == 0


def test_missing_file_is_not_recorded(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = _module(tmp_path, "alpha")
    _install(monkeypatch, {"alpha": {"root": root}})

    row = inspect_disease("alpha")
    assert row["categories"]["genetics"]["state"] == "not_recorded"
    assert row["provenance"]["evidence_records"] == 0


# ── Reference scheme classification ─────────────────────────────────────────


@pytest.mark.parametrize(
    ("reference", "expected_scheme"),
    [
        ("PMID:12345", "PMID"),
        ("REACTOME:R-HSA-977225", "REACTOME"),
        ("KEGG:hsa05010", "KEGG"),
        ("DOI:10.1000/xyz123", "DOI"),
    ],
)
def test_reference_schemes_classify_leading_prefix(reference: str, expected_scheme: str) -> None:
    assert _reference_schemes(reference) == [expected_scheme]


def test_free_text_reference_still_surfaces_embedded_trial_id() -> None:
    schemes = _reference_schemes("ACR 2024 Abstract; REGENCY Trial (NCT04252599)")
    assert schemes == ["NCT"]


def test_unclassifiable_reference_is_not_provenance() -> None:
    assert _reference_schemes("Internal curation note, no identifier") == ["UNCLASSIFIED"]
    assert _reference_schemes("") == ["UNCLASSIFIED"]


def test_by_scheme_counts_references_not_records(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _module(tmp_path, "alpha")
    _write(
        root,
        "genes.json",
        {"genes": [{"id": "G1", "references": ["PMID:1", "PMID:2", "REACTOME:R-HSA-1"]}]},
    )
    _install(monkeypatch, {"alpha": {"root": root}})

    row = inspect_disease("alpha")
    assert row["provenance"]["present"] == 1
    assert row["provenance"]["references"] == 3
    assert row["provenance"]["by_scheme"] == {"PMID": 2, "REACTOME": 1}


# ── Scaffold identification ─────────────────────────────────────────────────


def test_scaffold_detected_from_generator_marker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _module(tmp_path, "alpha")
    _write(root, "genes.json", {"genes": []})
    _install(
        monkeypatch,
        {
            "alpha": {
                "root": root,
                "profile": _FakeProfile("Alpha", "Alpha — AUTO-GENERATED SCAFFOLD; review."),
            }
        },
    )
    assert inspect_disease("alpha")["is_scaffold"] is True


def test_curated_module_is_not_labelled_scaffold(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _module(tmp_path, "alpha")
    _write(root, "genes.json", {"genes": []})
    _install(
        monkeypatch,
        {"alpha": {"root": root, "profile": _FakeProfile("Alpha", "Curated by a reviewer.")}},
    )
    assert inspect_disease("alpha")["is_scaffold"] is False


# ── Relationship edges: provenance is not applicable ────────────────────────


def test_relationships_are_excluded_from_provenance_denominator(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _module(tmp_path, "alpha")
    _write(root, "genes.json", {"genes": [{"id": "G1", "references": ["PMID:1"]}]})
    _write(
        root,
        "relationships.json",
        {
            "relationships": [
                {"source": "G1", "target": "P1", "type": "encodes"},
                {"source": "G2", "target": "P2", "type": "encodes"},
            ]
        },
    )
    _install(monkeypatch, {"alpha": {"root": root}})

    row = inspect_disease("alpha")
    assert row["categories"]["relationships"]["provenance"] == "not_applicable"
    assert row["categories"]["relationships"]["records"] == 2
    # Only the gene record is evidence-bearing.
    assert row["provenance"]["evidence_records"] == 1


# ── Safety profile file-level provenance ────────────────────────────────────


def test_safety_profile_absent_is_not_recorded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _module(tmp_path, "alpha")
    _install(monkeypatch, {"alpha": {"root": root}})

    entry = inspect_disease("alpha")["categories"]["safety_profiles"]
    assert entry["state"] == "not_recorded"
    assert entry["records"] == 0


def test_safety_profile_unparseable_is_invalid(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _module(tmp_path, "alpha")
    (root / "adverse_events.json").write_text("{not valid json", encoding="utf-8")
    _install(monkeypatch, {"alpha": {"root": root}})

    entry = inspect_disease("alpha")["categories"]["safety_profiles"]
    assert entry["state"] == "invalid"


def test_safety_profile_present_carries_file_provenance(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _module(tmp_path, "alpha")
    _write(
        root,
        "adverse_events.json",
        {
            "source": "disease_drug_safety_profile",
            "limitations": ["research heuristics only"],
            "profiles": [{"drug_id": "belimumab"}],
        },
    )
    _install(monkeypatch, {"alpha": {"root": root}})

    entry = inspect_disease("alpha")["categories"]["safety_profiles"]
    assert entry["state"] == "present"
    assert entry["records"] == 1
    assert entry["file_provenance"]["source"] == "disease_drug_safety_profile"
    assert entry["file_provenance"]["limitations"] == 1


# ── Report determinism ──────────────────────────────────────────────────────


def test_report_is_deterministic_except_generated_at(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    modules: dict[str, Any] = {}
    for name in ("alpha", "beta"):
        root = _module(tmp_path, name)
        _write(root, "genes.json", {"genes": [{"id": f"{name}-g", "references": ["PMID:1"]}]})
        modules[name] = {"root": root, "config": _full_config()}
    _install(monkeypatch, modules)

    first = build_evidence_coverage_report(disease_ids=["alpha", "beta"])
    second = build_evidence_coverage_report(disease_ids=["alpha", "beta"])

    assert first["schema"] == REPORT_SCHEMA
    assert first["fingerprint"] == second["fingerprint"]
    assert first["aggregate"] == second["aggregate"]
    assert "generated_at" in first
    assert "generated_at" in second


# ── Scope honesty: sample versus full population ────────────────────────────


def test_bounded_slice_never_claims_full_population(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _module(tmp_path, "alpha")
    _write(root, "genes.json", {"genes": []})
    _install(
        monkeypatch,
        {"alpha": {"root": root}},
        population=["alpha", "beta", "gamma", "delta", "epsilon"],
    )

    report = build_evidence_coverage_report(disease_ids=["alpha"])
    scope = report["scope"]

    assert scope["covers_full_population"] is False
    assert scope["coverage_basis"] == "bounded_unsampled_slice"
    assert scope["population_modules"] == 5
    assert scope["measured"] == 1
    assert scope["population_modules"] >= scope["measured"]


def test_sampled_selection_is_reproducible(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    modules: dict[str, Any] = {}
    for index in range(6):
        name = f"disease_{index:02d}"
        root = _module(tmp_path, name)
        _write(root, "genes.json", {"genes": []})
        modules[name] = {"root": root}
    _install(monkeypatch, modules)

    ids = list(modules)
    first = build_evidence_coverage_report(disease_ids=ids, sample_size=3, sample_seed=11)
    second = build_evidence_coverage_report(disease_ids=ids, sample_size=3, sample_seed=11)

    first_ids = [row["disease_id"] for row in first["per_disease"]]
    second_ids = [row["disease_id"] for row in second["per_disease"]]

    assert first_ids == second_ids
    assert len(first_ids) == 3
    assert first["scope"]["sample_size"] == 3
    assert first["scope"]["sample_seed"] == 11
    assert first["scope"]["coverage_basis"] == "sample"
    assert first["scope"]["covers_full_population"] is False


# ── Blocked slugs ───────────────────────────────────────────────────────────


def test_blocked_slug_is_excluded_and_counted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _module(tmp_path, "alpha")
    _write(root, "genes.json", {"genes": []})
    _install(monkeypatch, {"alpha": {"root": root}})

    report = build_evidence_coverage_report(disease_ids=["alpha", "zz_scaffold_test"])

    assert report["scope"]["excluded_blocked"] == 1
    assert [row["disease_id"] for row in report["per_disease"]] == ["alpha"]


# ── Researcher-facing summary ───────────────────────────────────────────────


def test_summary_states_sampling_limitation_and_fingerprint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _module(tmp_path, "alpha")
    _write(root, "genes.json", {"genes": [{"id": "G1", "references": ["PMID:1"]}]})
    _install(monkeypatch, {"alpha": {"root": root}}, population=["alpha", "beta"])

    report = build_evidence_coverage_report(disease_ids=["alpha"])
    summary = render_summary(report)

    assert "not a full-corpus measurement" in summary
    assert report["fingerprint"] in summary
    assert "Limitations" in summary
    # Absence must never be phrased as a measured zero.
    assert "Records with no citation field" in summary


# ── Failure isolation ───────────────────────────────────────────────────────


def test_failing_module_is_reported_not_swallowed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    good_root = _module(tmp_path, "alpha")
    _write(good_root, "genes.json", {"genes": []})
    broken_root = _module(tmp_path, "beta")
    _install(
        monkeypatch,
        {
            "alpha": {"root": good_root},
            "beta": {"root": broken_root, "fail": True},
        },
    )

    report = build_evidence_coverage_report(disease_ids=["alpha", "beta"])

    assert report["scope"]["requested"] == 2
    assert report["scope"]["measured"] == 1
    assert [row["disease_id"] for row in report["per_disease"]] == ["alpha"]
    assert len(report["scope"]["errors"]) == 1
    assert report["scope"]["errors"][0]["disease_id"] == "beta"
    assert "RuntimeError" in report["scope"]["errors"][0]["error"]


# ── Persistence ─────────────────────────────────────────────────────────────


def test_report_writer_round_trips_canonical_json(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _module(tmp_path, "alpha")
    _write(root, "genes.json", {"genes": []})
    _install(monkeypatch, {"alpha": {"root": root}})

    report = build_evidence_coverage_report(disease_ids=["alpha"])
    out = write_evidence_coverage_report(report, tmp_path / "reports" / "coverage.json")

    reloaded = json.loads(out.read_text(encoding="utf-8"))
    assert reloaded["fingerprint"] == report["fingerprint"]
    assert reloaded["schema"] == REPORT_SCHEMA
