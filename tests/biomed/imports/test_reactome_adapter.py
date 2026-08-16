"""Unit tests for ReactomeImportAdapter."""

from __future__ import annotations

from pathlib import Path

from med_research.biomed.imports.reactome_adapter import ReactomeImportAdapter
from med_research.biomed.imports.service import ImportService
from med_research.biomed.models import EntityType, Predicate, ResourcePolicy
from med_research.biomed.repository import BiomedicalRepository


def test_reactome_adapter_json_parsing(tmp_path: Path) -> None:
    fixture_path = Path("tests/fixtures/biomed/reactome_sample.json")
    adapter = ReactomeImportAdapter()
    policy = ResourcePolicy(resource_name="reactome", redistribution_policy="permitted")

    bundle = adapter.parse(fixture_path, policy, version="v89")

    assert bundle.snapshot.resource_name == "reactome"
    assert bundle.counts.entities >= 2
    assert bundle.counts.claims >= 3
    assert bundle.counts.evidence >= 3

    curies = {e.primary_curie for e in bundle.entities}
    assert "REACTOME:R-HSA-168898" in curies
    assert "REACTOME:R-HSA-1280215" in curies
    assert "HGNC:TNF" in curies

    claims = {(c.subject_curie, c.predicate, c.object_curie) for c in bundle.claims}
    assert ("REACTOME:R-HSA-1280215", Predicate.PART_OF, "REACTOME:R-HSA-168898") in claims
    assert ("HGNC:TNF", Predicate.INVOLVES_PATHWAY, "REACTOME:R-HSA-168898") in claims


def test_reactome_adapter_tsv_parsing(tmp_path: Path) -> None:
    tsv_content = (
        "P01375\tR-HSA-168898\thttps://reactome.org/PathwayBrowser/#/R-HSA-168898\t"
        "Innate Immune System\tTAS\tHomo sapiens\n"
    )
    tsv_file = tmp_path / "reactome_test.tsv"
    tsv_file.write_text(tsv_content, encoding="utf-8")

    adapter = ReactomeImportAdapter()
    policy = ResourcePolicy(resource_name="reactome", redistribution_policy="permitted")
    bundle = adapter.parse(tsv_file, policy)

    assert len(bundle.entities) >= 2
    assert len(bundle.claims) == 1
    assert bundle.claims[0].predicate == Predicate.INVOLVES_PATHWAY
    assert bundle.claims[0].subject_curie == "UNIPROT:P01375"
    assert bundle.claims[0].object_curie == "REACTOME:R-HSA-168898"


def test_reactome_import_service_roundtrip(repository: BiomedicalRepository) -> None:
    fixture_path = Path("tests/fixtures/biomed/reactome_sample.json")
    adapter = ReactomeImportAdapter()
    policy = ResourcePolicy(resource_name="reactome", redistribution_policy="permitted")

    bundle = adapter.parse(fixture_path, policy)
    service = ImportService(repository)
    report = service.import_bundle(bundle, activate=True)

    assert report.resource_name == "reactome"

    # Query repository
    ent = repository.get_entity("REACTOME:R-HSA-168898")
    assert ent is not None
    assert ent.entity.entity_type == EntityType.PATHWAY
    assert ent.revision is not None
    assert ent.revision.label == "Innate Immune System"
