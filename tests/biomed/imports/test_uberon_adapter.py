"""Unit tests for UberonImportAdapter."""

from __future__ import annotations

from pathlib import Path

from med_research.biomed.imports.service import ImportService
from med_research.biomed.imports.uberon_adapter import UberonImportAdapter
from med_research.biomed.models import EntityType, Predicate, ResourcePolicy
from med_research.biomed.repository import BiomedicalRepository


def test_uberon_adapter_json_parsing(tmp_path: Path) -> None:
    fixture_path = Path("tests/fixtures/biomed/uberon_sample.json")
    adapter = UberonImportAdapter()
    policy = ResourcePolicy(resource_name="uberon", redistribution_policy="permitted")

    bundle = adapter.parse(fixture_path, policy, version="2026-01")

    assert bundle.snapshot.resource_name == "uberon"
    assert bundle.counts.entities >= 3

    curies = {e.primary_curie for e in bundle.entities}
    assert "UBERON:0000955" in curies
    assert "UBERON:0000956" in curies
    assert "CL:0000084" in curies

    claims = {(c.subject_curie, c.predicate, c.object_curie) for c in bundle.claims}
    assert ("UBERON:0000956", Predicate.PART_OF, "UBERON:0000955") in claims
    assert ("HGNC:TNF", Predicate.EXPRESSED_IN, "UBERON:0000955") in claims


def test_uberon_adapter_obo_parsing(tmp_path: Path) -> None:
    obo_content = """format-version: 1.2

[Term]
id: UBERON:0000956
name: cerebral cortex
relationship: part_of UBERON:0000955 ! brain

[Term]
id: UBERON:0000955
name: brain
"""
    obo_file = tmp_path / "uberon_test.obo"
    obo_file.write_text(obo_content, encoding="utf-8")

    adapter = UberonImportAdapter()
    policy = ResourcePolicy(resource_name="uberon", redistribution_policy="permitted")
    bundle = adapter.parse(obo_file, policy)

    assert len(bundle.entities) == 2
    assert len(bundle.claims) == 1
    assert bundle.claims[0].predicate == Predicate.PART_OF


def test_uberon_import_service_roundtrip(repository: BiomedicalRepository) -> None:
    fixture_path = Path("tests/fixtures/biomed/uberon_sample.json")
    adapter = UberonImportAdapter()
    policy = ResourcePolicy(resource_name="uberon", redistribution_policy="permitted")

    bundle = adapter.parse(fixture_path, policy)
    service = ImportService(repository)
    report = service.import_bundle(bundle, activate=True)

    assert report.resource_name == "uberon"

    # Query repository
    ent = repository.get_entity("CL:0000084")
    assert ent is not None
    assert ent.entity.entity_type == EntityType.CELL_TYPE
    assert ent.revision is not None
    assert ent.revision.label == "T cell"
