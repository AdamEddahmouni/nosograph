"""Integration tests for ClinVar and OpenFDA live API adapters."""

from __future__ import annotations

import json
from pathlib import Path

from med_research.biomed.imports.clinvar_adapter import ClinVarImportAdapter
from med_research.biomed.imports.openfda_adapter import OpenFDAImportAdapter
from med_research.biomed.imports.service import ImportService
from med_research.biomed.models import EvidenceDirection, Predicate, ResourcePolicy
from med_research.biomed.repository import BiomedicalRepository


def test_clinvar_adapter_parse_and_import(tmp_path: Path, repository: BiomedicalRepository) -> None:
    data = [
        {
            "vcv_id": "VCV000001",
            "gene_symbol": "STAT4",
            "gene_id": "6775",
            "condition_curie": "MONDO:0007915",
            "condition_name": "Systemic Lupus Erythematosus",
            "clinical_significance": "Pathogenic",
        },
        {
            "vcv_id": "VCV000002",
            "gene_symbol": "PTPN22",
            "gene_id": "26191",
            "condition_curie": "MONDO:0007915",
            "condition_name": "Systemic Lupus Erythematosus",
            "clinical_significance": "Benign",
        },
    ]
    file_path = tmp_path / "clinvar_sample.json"
    file_path.write_text(json.dumps(data), encoding="utf-8")

    policy = ResourcePolicy(
        resource_name="clinvar",
        license_id="Public Domain",
        redistribution_policy="permitted",
    )

    adapter = ClinVarImportAdapter()
    assert adapter.resource_name == "clinvar"
    assert "json" in adapter.supported_formats

    bundle = adapter.parse(file_path, policy=policy, version="2026.1")
    assert len(bundle.entities) >= 3  # STAT4, PTPN22, MONDO:0007915
    assert len(bundle.claims) == 2
    assert len(bundle.evidence) == 2

    # Verify ingestion into canonical repository
    service = ImportService(repository)
    report = service.import_bundle(bundle)
    assert report.counts.claims == 2
    assert report.counts.evidence == 2

    # Query claims and evidence
    claims = repository.list_claims("MONDO:0007915", predicate=Predicate.ASSOCIATED_WITH_GENE)
    assert len(claims) == 2

    supp_evidence = bundle.evidence[0]
    assert supp_evidence.direction == EvidenceDirection.SUPPORTING

    contra_evidence = bundle.evidence[1]
    assert contra_evidence.direction == EvidenceDirection.CONTRADICTORY


def test_openfda_adapter_parse_and_import(tmp_path: Path, repository: BiomedicalRepository) -> None:
    data = {
        "results": [
            {
                "drug_name": "HYDROXYCHLOROQUINE",
                "pubchem_cid": 3652,
                "condition_curie": "MONDO:0007915",
                "condition_name": "Systemic Lupus Erythematosus",
                "report_id": "FDA10001",
                "record_type": "indication",
            },
            {
                "drug_name": "HYDROXYCHLOROQUINE",
                "pubchem_cid": 3652,
                "condition_curie": "MONDO:0005359",
                "condition_name": "Retinopathy",
                "report_id": "FDA10002",
                "record_type": "adverse_event",
            },
        ]
    }
    file_path = tmp_path / "openfda_sample.json"
    file_path.write_text(json.dumps(data), encoding="utf-8")

    policy = ResourcePolicy(
        resource_name="openfda",
        license_id="CC0-1.0",
        redistribution_policy="permitted",
    )

    adapter = OpenFDAImportAdapter()
    assert adapter.resource_name == "openfda"
    assert "json" in adapter.supported_formats

    bundle = adapter.parse(file_path, policy=policy, version="2026.1")
    assert len(bundle.entities) >= 3  # PUBCHEM.COMPOUND:3652, MONDO:0007915, MONDO:0005359
    assert len(bundle.claims) == 2
    assert len(bundle.evidence) == 2

    service = ImportService(repository)
    report = service.import_bundle(bundle)
    assert report.counts.claims == 2
    assert report.counts.evidence == 2

    # Check indication claim
    treated_claims = repository.list_claims("MONDO:0007915", predicate=Predicate.TREATED_BY)
    assert len(treated_claims) == 1
    assert treated_claims[0].object_curie == "PUBCHEM.COMPOUND:3652"

    # Check adverse event claim
    adverse_claims = repository.list_claims(
        "MONDO:0005359", predicate=Predicate.ASSOCIATED_WITH_EXPOSURE
    )
    assert len(adverse_claims) == 1
