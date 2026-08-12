"""Unit tests for Alzheimer's Disease (ad) disease module."""

from __future__ import annotations

import pytest

from med_research.diseases.base import Disease


def test_ad_disease_discovery():
    assert "ad" in Disease.list_all()


def test_ad_disease_loading():
    disease = Disease("ad")
    assert disease.disease_id == "ad"
    assert disease.profile.name == "Alzheimer's Disease"
    assert "Abeta42" in disease.profile.hallmark_markers

    genes = disease.load_genes()
    assert "genes" in genes
    gene_ids = {g["id"] for g in genes["genes"]}
    assert "APOE" in gene_ids
    assert "APP" in gene_ids
    assert "MAPT" in gene_ids

    drugs = disease.load_drugs()
    assert "drugs" in drugs
    drug_ids = {d["id"] for d in drugs["drugs"]}
    assert "donepezil" in drug_ids
    assert "lecanemab" in drug_ids

    pathways = disease.load_pathways()
    assert "pathways" in pathways
    assert len(pathways["pathways"]) > 0

    relationships = disease.load_relationships()
    assert "relationships" in relationships
    assert len(relationships["relationships"]) > 0


def test_ad_disease_validation():
    disease = Disease("ad")
    checks = disease.validate()
    for field, status in checks.items():
        assert status == "ok", f"Field '{field}' failed validation with status: {status}"
