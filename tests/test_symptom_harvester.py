"""Tests for HPO / OT symptom harvesting."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from med_research.diseases.bulk_store import OpenTargetsBulkStore, manifest_path
from med_research.diseases.symptom_harvester import (
    harvest_symptoms_for_disease,
    local_symptom_source_availability,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "opentargets" / "25.03"


class _PhenotypeTableStore:
    def __init__(self, tables: set[str]) -> None:
        self.tables = tables
        self.checked: list[str] = []

    def _parquet_glob(self, table: str) -> str | None:
        self.checked.append(table)
        return f"/local/{table}.parquet" if table in self.tables else None

    def _glob_column_names(
        self,
        _glob: str,
        *,
        raise_on_error: bool = False,
        refresh: bool = False,
    ) -> set[str]:
        return {"diseaseId", "phenotypeLabel"}


def _create_hpoa_availability_db(path: Path, *, active: bool) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE active_snapshots (resource_name TEXT, snapshot_id TEXT);
            CREATE TABLE claims (id TEXT);
            CREATE TABLE claim_evidence (id TEXT);
            """
        )
        if active:
            conn.execute(
                "INSERT INTO active_snapshots(resource_name, snapshot_id) VALUES ('hpoa', 'active')"
            )


@pytest.mark.parametrize(
    ("database", "active", "tables", "expected_hpoa", "expected_ot"),
    [
        ("present", True, {"disease_phenotype"}, True, True),
        ("present", False, {"disease_phenotype"}, False, True),
        ("present", True, {"disease", "known_drug"}, True, False),
        ("missing", False, {"disease_phenotype"}, False, True),
    ],
)
def test_local_symptom_source_availability(
    tmp_path: Path,
    database: str,
    active: bool,
    tables: set[str],
    expected_hpoa: bool,
    expected_ot: bool,
) -> None:
    db_path = tmp_path / "biomedical.sqlite3"
    if database == "present":
        _create_hpoa_availability_db(db_path, active=active)
    store = _PhenotypeTableStore(tables)

    availability = local_symptom_source_availability(store=store, biomedical_db_path=db_path)

    assert availability == {"biomed_hpoa": expected_hpoa, "ot_phenotype": expected_ot}
    assert store.checked == ["disease_phenotype"]


def test_local_symptom_source_availability_rejects_missing_hpoa_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "incomplete.sqlite3"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE active_snapshots (resource_name TEXT, snapshot_id TEXT)")
        conn.execute("INSERT INTO active_snapshots VALUES ('hpoa', 'active')")

    availability = local_symptom_source_availability(
        store=_PhenotypeTableStore(set()), biomedical_db_path=db_path
    )

    assert availability["biomed_hpoa"] is False
    assert availability["ot_phenotype"] is False


@pytest.fixture(scope="module")
def store(tmp_path_factory) -> OpenTargetsBulkStore:
    tmp = tmp_path_factory.mktemp("symptom_bulk")
    bulk_root = tmp / "opentargets"
    version_dir = bulk_root / "25.03"
    import shutil

    if not FIXTURES.is_dir():
        from tests.fixtures.opentargets.build_fixtures import main as build

        build()
    shutil.copytree(FIXTURES, version_dir)
    manifest_path(bulk_root).parent.mkdir(parents=True, exist_ok=True)
    manifest_path(bulk_root).write_text(json.dumps({"version": "25.03"}), encoding="utf-8")
    return OpenTargetsBulkStore(bulk_root=bulk_root, version="25.03")


def test_harvest_symptoms_from_ot(tmp_path: Path, store: OpenTargetsBulkStore, monkeypatch) -> None:
    from med_research.diseases import scaffold as scaffold_mod

    diseases_root = tmp_path / "diseases"
    disease_dir = diseases_root / "ra_sym"
    disease_dir.mkdir(parents=True)
    config = disease_dir / "config.py"
    config.write_text(
        'PIPELINE_LABEL = "RA"\nSYMPTOMS = []\nPUBMED_QUERIES = []\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(scaffold_mod, "_diseases_root", lambda: diseases_root)
    monkeypatch.setattr(
        "med_research.diseases.symptom_harvester.load_disease_registry",
        lambda *a, **k: [{"id": "ra_sym", "name": "Rheumatoid Arthritis", "efo_id": "EFO_0001370"}],
    )
    monkeypatch.setattr(
        "med_research.diseases.symptom_harvester._diseases_root",
        lambda: diseases_root,
    )

    result = harvest_symptoms_for_disease("ra_sym", store=store, write=True)
    assert result["symptoms"]
    assert "Arthritis" in result["symptoms"]
    text = config.read_text(encoding="utf-8")
    assert "Arthritis" in text
    assert "SYMPTOMS = []" not in text


def test_hpo_harvester_reads_active_positive_hpoa_only(tmp_path: Path, monkeypatch) -> None:
    from med_research.diseases import symptom_harvester as harvester
    from med_research.web import config as web_config

    db_path = tmp_path / "biomedical.sqlite3"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE resource_snapshots (id TEXT PRIMARY KEY, resource_name TEXT NOT NULL);
            CREATE TABLE active_snapshots (resource_name TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL);
            CREATE TABLE claims (
                id TEXT PRIMARY KEY,
                subject_curie TEXT NOT NULL,
                object_curie TEXT NOT NULL,
                predicate TEXT NOT NULL,
                qualifiers_json TEXT NOT NULL DEFAULT '{}',
                supersedes_claim_id TEXT
            );
            CREATE TABLE claim_evidence (
                id TEXT PRIMARY KEY,
                claim_id TEXT NOT NULL,
                snapshot_id TEXT NOT NULL,
                direction TEXT NOT NULL
            );
            """
        )
        conn.executemany(
            "INSERT INTO resource_snapshots(id, resource_name) VALUES (?, ?)",
            [("hpoa-old", "hpoa"), ("hpoa-active", "hpoa")],
        )
        conn.execute(
            "INSERT INTO active_snapshots(resource_name, snapshot_id) VALUES ('hpoa', 'hpoa-active')"
        )
        records = [
            # Current positive symptom evidence is retained.
            ("current", "MONDO:0000001", "HP:0000001", '{"frequency":"4/5","negated":false}', None),
            # A negated term is not a symptom.
            ("negative", "MONDO:0000001", "HP:0000002", '{"negated":true}', None),
            # No ontology label: raw CURIE must never leak into config.
            ("unlabeled", "MONDO:0000001", "HP:0000003", "{}", None),
            # Inheritance and onset are metadata, not clinical manifestations.
            ("inheritance", "MONDO:0000001", "HP:0000004", "{}", None),
            ("onset", "MONDO:0000001", "HP:0000005", "{}", None),
            # Inactive evidence and unsupported directions are not current.
            ("stale", "MONDO:0000001", "HP:0000006", "{}", None),
            ("contradictory", "MONDO:0000001", "HP:0000007", "{}", None),
            # Superseded claims are ignored even if their evidence is active.
            ("superseded", "MONDO:0000001", "HP:0000008", "{}", None),
            ("replacement", "MONDO:0000001", "HP:0000009", "{}", "superseded"),
        ]
        conn.executemany(
            "INSERT INTO claims(id, subject_curie, object_curie, predicate, qualifiers_json, supersedes_claim_id) "
            "VALUES (?, ?, ?, 'HAS_PHENOTYPE', ?, ?)",
            [
                (claim_id, subject, obj, qualifiers, supersedes)
                for claim_id, subject, obj, qualifiers, supersedes in records
            ],
        )
        evidence = [
            ("ev-current", "current", "hpoa-active", "supporting"),
            ("ev-negative", "negative", "hpoa-active", "supporting"),
            ("ev-unlabeled", "unlabeled", "hpoa-active", "supporting"),
            ("ev-inheritance", "inheritance", "hpoa-active", "supporting"),
            ("ev-onset", "onset", "hpoa-active", "supporting"),
            ("ev-stale", "stale", "hpoa-old", "supporting"),
            ("ev-contradictory", "contradictory", "hpoa-active", "contradictory"),
            ("ev-superseded", "superseded", "hpoa-active", "supporting"),
            ("ev-replacement", "replacement", "hpoa-active", "supporting"),
        ]
        conn.executemany(
            "INSERT INTO claim_evidence(id, claim_id, snapshot_id, direction) VALUES (?, ?, ?, ?)",
            evidence,
        )

    monkeypatch.setattr(web_config, "BIOMEDICAL_DB_PATH", db_path)
    monkeypatch.setattr(
        harvester,
        "_hpo_label_map",
        lambda: {
            "HP_0000001": "Current labeled symptom",
            "HP_0000002": "Negated symptom",
            "HP_0000004": "Autosomal dominant inheritance",
            "HP_0000005": "Childhood onset",
            "HP_0000006": "Stale symptom",
            "HP_0000007": "Contradictory symptom",
            "HP_0000008": "Superseded symptom",
        },
    )

    assert harvester._hpo_symptoms_from_biomed("MONDO:0000001") == ["Current labeled symptom"]


def test_hpo_harvester_can_raise_source_query_errors(tmp_path: Path, monkeypatch) -> None:
    from med_research.diseases import symptom_harvester as harvester
    from med_research.web import config as web_config

    db_path = tmp_path / "invalid.sqlite3"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE active_snapshots (resource_name TEXT, snapshot_id TEXT);
            CREATE TABLE claims (id TEXT);
            CREATE TABLE claim_evidence (id TEXT);
            INSERT INTO active_snapshots VALUES ('hpoa', 'active');
            """
        )
    monkeypatch.setattr(web_config, "BIOMEDICAL_DB_PATH", db_path)

    with pytest.raises(sqlite3.OperationalError):
        harvester._hpo_symptoms_from_biomed("MONDO:0000001", raise_on_error=True)


def test_hpo_harvester_normalizes_ot_style_mondo_curie(tmp_path: Path, monkeypatch) -> None:
    from med_research.diseases import symptom_harvester as harvester
    from med_research.web import config as web_config

    db_path = tmp_path / "empty.sqlite3"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE active_snapshots (resource_name TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL);
            CREATE TABLE claims (
                id TEXT PRIMARY KEY,
                subject_curie TEXT NOT NULL,
                object_curie TEXT NOT NULL,
                predicate TEXT NOT NULL,
                qualifiers_json TEXT NOT NULL DEFAULT '{}',
                supersedes_claim_id TEXT
            );
            CREATE TABLE claim_evidence (
                id TEXT PRIMARY KEY,
                claim_id TEXT NOT NULL,
                snapshot_id TEXT NOT NULL,
                direction TEXT NOT NULL
            );
            INSERT INTO active_snapshots(resource_name, snapshot_id) VALUES ('hpoa', 'active');
            """
        )
    monkeypatch.setattr(web_config, "BIOMEDICAL_DB_PATH", db_path)
    monkeypatch.setattr(
        harvester,
        "_hpo_label_map",
        lambda: {},
    )

    # No matching subject is intentionally present; the alternate CURIE spelling
    # must simply result in an empty harvest rather than a query failure.
    assert harvester._hpo_symptoms_from_biomed("MONDO_0000001") == []
