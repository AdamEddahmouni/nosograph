"""Tests for schema-validated loading of knowledge-graph JSON files.

Verifies that the curated genes/drugs/pathways/relationships/profile files
are validated against the Pydantic schemas in ``diseases.schemas`` at the
two central load boundaries:

* ``med_research.pipeline.knowledge_graph.config`` (used by every pipeline
  module), and
* ``med_research.diseases.base.Disease`` (used by the web layer, CLI,
  coverage, and workspace).

Also verifies the typed error contract (``MissingDataError`` /
``SchemaValidationError``), lossless round-tripping of disease-specific
evidence keys, and that existing tolerant call sites still degrade
gracefully.
"""

import json
from pathlib import Path

import pytest

from med_research.diseases.base import Disease
from med_research.exceptions import (
    DataValidationError,
    MissingDataError,
    SchemaValidationError,
)

DISEASES = ["sle", "ra", "ms", "ss", "ssc", "t1d", "ibd"]
KG_FILES = ["genes.json", "drugs.json", "pathways.json", "relationships.json", "profile.json"]

pytestmark = pytest.mark.unit




# ── Happy path: every disease validates through both boundaries ──────────


@pytest.mark.parametrize("disease_id", DISEASES)
@pytest.mark.parametrize("filename", KG_FILES)
def test_config_loader_validates_every_disease_file(disease_id, filename):
    from med_research.pipeline.knowledge_graph.config import load_disease_json

    payload = load_disease_json(disease_id, filename)
    assert isinstance(payload, dict)
    if filename == "profile.json":
        assert payload["id"]
        assert payload["name"]
    else:
        key = Path(filename).stem
        assert key in payload
        assert isinstance(payload[key], list)


@pytest.mark.parametrize("disease_id", DISEASES)
def test_disease_boundary_validates_all_files(disease_id):
    disease = Disease(disease_id)
    assert isinstance(disease.load_genes(), dict)
    assert isinstance(disease.load_drugs(), dict)
    assert isinstance(disease.load_pathways(), dict)
    assert isinstance(disease.load_relationships(), dict)
    assert disease.profile.name  # validated profile property


@pytest.mark.parametrize("disease_id", DISEASES)
def test_genes_have_required_fields_after_validation(disease_id):
    from med_research.pipeline.knowledge_graph.config import load_genes

    genes = load_genes(disease_id)["genes"]
    assert genes
    for gene in genes:
        assert gene["id"]
        assert gene["name"]
        assert gene["chromosome"]
        assert gene["function"]


# ── Lossless round-trip: disease-specific evidence keys survive ──────────


def test_ibd_evidence_key_survives_validation():
    from med_research.pipeline.knowledge_graph.config import load_genes

    genes = load_genes("ibd")["genes"]
    first = next(g for g in genes if g.get("ibd_evidence"))
    assert first["ibd_evidence"]


@pytest.mark.parametrize(
    ("disease_id", "key"),
    [
        ("sle", "lupus_evidence"),
        ("ra", "ra_evidence"),
        ("ms", "ms_evidence"),
        ("ss", "ss_evidence"),
        ("ssc", "ssc_evidence"),
        ("t1d", "t1d_evidence"),
    ],
)
def test_disease_evidence_key_survives_validation(disease_id, key):
    from med_research.pipeline.knowledge_graph.config import load_genes

    genes = load_genes(disease_id)["genes"]
    assert any(g.get(key) for g in genes)


def test_unknown_extra_keys_are_preserved():
    """Validation is a gate; unknown curated keys are not dropped."""
    import tempfile

    from med_research.diseases.schemas import GenesFile, load_validated_json

    payload = {
        "genes": [
            {
                "id": "X1",
                "name": "Fixture Gene",
                "chromosome": "1p",
                "function": "test",
                "custom_disease_specific_key": "kept",
            }
        ]
    }
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "genes.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        loaded = load_validated_json(path, GenesFile)
    assert loaded["genes"][0]["custom_disease_specific_key"] == "kept"


# ── Typed error contract ─────────────────────────────────────────────────


def test_missing_file_raises_missing_data_error(tmp_path):
    from med_research.diseases.schemas import GenesFile, load_validated_json

    with pytest.raises(MissingDataError) as excinfo:
        load_validated_json(tmp_path / "genes.json", GenesFile)
    assert "not found" in str(excinfo.value)
    # Backward compatibility: callers catching FileNotFoundError still work.
    assert isinstance(excinfo.value, FileNotFoundError)
    assert isinstance(excinfo.value, DataValidationError)
    # FileNotFoundError-style handlers can read the filename attribute.
    assert excinfo.value.filename == str(tmp_path / "genes.json")


def test_malformed_json_raises_schema_validation_error(tmp_path):
    from med_research.diseases.schemas import GenesFile, load_validated_json

    path = tmp_path / "genes.json"
    path.write_text("{ not valid json !!!", encoding="utf-8")
    with pytest.raises(SchemaValidationError) as excinfo:
        load_validated_json(path, GenesFile)
    assert "Invalid JSON" in str(excinfo.value)
    assert isinstance(excinfo.value, ValueError)
    assert isinstance(excinfo.value, DataValidationError)


def test_schema_violation_raises_schema_validation_error(tmp_path):
    from med_research.diseases.schemas import GenesFile, load_validated_json

    path = tmp_path / "genes.json"
    path.write_text(json.dumps({"genes": [{"id": "missing-fields"}]}), encoding="utf-8")
    with pytest.raises(SchemaValidationError) as excinfo:
        load_validated_json(path, GenesFile)
    assert "Schema validation failed" in str(excinfo.value)
    assert "genes.json" in str(excinfo.value)


def test_config_loader_missing_file_keeps_filenotfound_contract():
    from med_research.pipeline.knowledge_graph.config import load_disease_json

    with pytest.raises(FileNotFoundError):
        load_disease_json("sle", "does_not_exist.json")


def test_disease_missing_file_raises_typed_error(monkeypatch, tmp_path):
    """Disease.load_json routes registered files through the strict loader."""
    monkeypatch.setattr(
        Disease,
        "data_dir",
        property(lambda self: tmp_path),
    )
    with pytest.raises(MissingDataError):
        Disease("sle").load_genes()


# ── Lenient legacy wrapper ───────────────────────────────────────────────


def test_validate_and_load_returns_none_on_failure(tmp_path):
    from med_research.diseases.schemas import GenesFile, validate_and_load

    assert validate_and_load(tmp_path / "missing.json", GenesFile) is None
    bad = tmp_path / "bad.json"
    bad.write_text("{ nope", encoding="utf-8")
    assert validate_and_load(bad, GenesFile) is None


def test_validate_and_load_returns_payload_on_success(tmp_path):
    from med_research.diseases.schemas import GenesFile, validate_and_load

    path = tmp_path / "genes.json"
    path.write_text(json.dumps({"genes": []}), encoding="utf-8")
    assert validate_and_load(path, GenesFile) == {"genes": []}


# ── Tolerant call sites still degrade gracefully ─────────────────────────


def test_cross_disease_tolerates_schema_invalid_disease(tmp_path, monkeypatch):
    """One broken disease must not kill the whole cross-disease load."""
    import med_research.pipeline.cross_disease.analyzer as analyzer

    def broken_loader(disease_id="sle"):
        raise SchemaValidationError(f"Schema validation failed for {disease_id}")

    monkeypatch.setattr(analyzer, "load_genes", broken_loader)
    monkeypatch.setattr(analyzer, "load_drugs", broken_loader)
    monkeypatch.setattr(analyzer, "load_pathways", broken_loader)
    monkeypatch.setattr(analyzer, "load_relationships", broken_loader)
    monkeypatch.setattr(
        analyzer,
        "list_diseases",
        lambda: {"sle": {"name": "SLE", "profile": {"id": "sle", "name": "SLE"}}},
    )

    data = analyzer.load_all_disease_data()
    assert data["sle"]["genes"] == {"genes": []}
    assert data["sle"]["drugs"] == {"drugs": []}


# ── Disease.validate() KG file checks ────────────────────────────────────


@pytest.mark.parametrize("disease_id", DISEASES)
def test_validate_reports_all_kg_files_ok(disease_id):
    disease = Disease(disease_id)
    checks = disease.validate()
    for field in ("genes", "drugs", "pathways", "relationships", "profile"):
        assert checks[field] == "ok"


def test_validate_reports_invalid_kg_file(tmp_path, monkeypatch):
    import json

    bad_genes = tmp_path / "genes.json"
    bad_genes.write_text(json.dumps({"genes": [{"id": "missing-fields"}]}), encoding="utf-8")

    monkeypatch.setattr(
        Disease,
        "data_dir",
        property(lambda self: tmp_path),
    )
    checks = Disease("sle").validate()
    assert checks["genes"].startswith("invalid:")


def test_validate_reports_missing_kg_file(tmp_path, monkeypatch):
    monkeypatch.setattr(
        Disease,
        "data_dir",
        property(lambda self: tmp_path),
    )
    checks = Disease("sle").validate()
    assert checks["genes"] == "missing"


def test_adverse_events_file_validates_for_all_diseases():
    from med_research.diseases.schemas import AdverseEventsFile, validate_and_load

    for disease_id in DISEASES:
        disease = Disease(disease_id)
        path = disease.data_dir / "adverse_events.json"
        if not path.is_file():
            continue
        payload = validate_and_load(path, AdverseEventsFile)
        assert payload is not None
        assert payload["disease_id"] == disease_id


def test_disease_validate_strict_fails_on_invalid_kg(monkeypatch, tmp_path):
    """CLI --strict must exit non-zero when validate() reports invalid KG files."""
    import json

    from med_research.cli import _build_parser, cmd_disease

    (tmp_path / "profile.json").write_text(
        json.dumps({"id": "sle", "name": "SLE", "kg_node_id": "SLE"}),
        encoding="utf-8",
    )
    (tmp_path / "drugs.json").write_text(json.dumps({"drugs": []}), encoding="utf-8")
    (tmp_path / "pathways.json").write_text(json.dumps({"pathways": []}), encoding="utf-8")
    (tmp_path / "relationships.json").write_text(
        json.dumps({"relationships": []}), encoding="utf-8"
    )
    (tmp_path / "genes.json").write_text(
        json.dumps({"genes": [{"id": "missing-fields"}]}), encoding="utf-8"
    )

    monkeypatch.setattr(
        Disease,
        "data_dir",
        property(lambda self: tmp_path),
    )
    monkeypatch.setattr(
        Disease,
        "discover",
        staticmethod(lambda: {"sle": Disease("sle")}),
    )

    parser = _build_parser()
    assert cmd_disease(parser.parse_args(["disease", "validate", "sle", "--strict"])) == 1
