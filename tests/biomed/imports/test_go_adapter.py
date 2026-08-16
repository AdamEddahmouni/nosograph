"""Unit tests for GOImportAdapter."""

from __future__ import annotations

from pathlib import Path

from med_research.biomed.imports.go_adapter import GOImportAdapter
from med_research.biomed.imports.service import ImportService
from med_research.biomed.models import EntityType, Predicate, ResourcePolicy
from med_research.biomed.repository import BiomedicalRepository


def test_go_adapter_json_parsing(tmp_path: Path) -> None:
    fixture_path = Path("tests/fixtures/biomed/go_sample.json")
    adapter = GOImportAdapter()
    policy = ResourcePolicy(resource_name="go", redistribution_policy="permitted")

    bundle = adapter.parse(fixture_path, policy, version="2026-01")

    assert bundle.snapshot.resource_name == "go"
    assert bundle.counts.entities >= 2
    assert bundle.counts.claims >= 1
    assert bundle.counts.evidence >= 1

    entity_curies = {e.primary_curie for e in bundle.entities}
    assert "GO:0006954" in entity_curies
    assert "GO:0002376" in entity_curies

    claims = {(c.subject_curie, c.predicate, c.object_curie) for c in bundle.claims}
    assert ("GO:0006954", Predicate.IS_A, "GO:0002376") in claims
    assert ("HGNC:TNF", Predicate.INVOLVES_PATHWAY, "GO:0006954") in claims


def test_go_adapter_obo_parsing(tmp_path: Path) -> None:
    obo_content = """format-version: 1.2
data-version: releases/2026-01-01

[Term]
id: GO:0006954
name: inflammatory response
namespace: biological_process
def: "The complex biological response of body tissues." [GOC:curators]
is_a: GO:0002376 ! immune system process

[Term]
id: GO:0002376
name: immune system process
namespace: biological_process
def: "Any process that can occur as part of immune system function." []
"""
    obo_file = tmp_path / "go_test.obo"
    obo_file.write_text(obo_content, encoding="utf-8")

    adapter = GOImportAdapter()
    policy = ResourcePolicy(resource_name="go", redistribution_policy="permitted")
    bundle = adapter.parse(obo_file, policy)

    assert len(bundle.entities) == 2
    assert len(bundle.claims) == 1
    assert bundle.claims[0].predicate == Predicate.IS_A


def test_go_import_service_roundtrip(repository: BiomedicalRepository) -> None:
    fixture_path = Path("tests/fixtures/biomed/go_sample.json")
    adapter = GOImportAdapter()
    policy = ResourcePolicy(resource_name="go", redistribution_policy="permitted")

    bundle = adapter.parse(fixture_path, policy)
    service = ImportService(repository)
    report = service.import_bundle(bundle, activate=True)

    assert report.resource_name == "go"
    assert report.counts.entities >= 2

    # Verify repository query
    ent = repository.get_entity("GO:0006954")
    assert ent is not None
    assert ent.entity.entity_type == EntityType.PATHWAY
    assert ent.revision is not None
    assert ent.revision.label == "inflammatory response"
