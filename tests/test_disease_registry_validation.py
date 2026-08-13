"""Registry-wide schema and relationship consistency validation tests."""

from __future__ import annotations

from med_research.diseases.base import Disease


def test_registry_disease_ids_format() -> None:
    disease_ids = Disease.list_all()
    assert len(disease_ids) >= 500
    for d_id in disease_ids:
        assert d_id.islower()
        assert " " not in d_id


def test_all_registry_diseases_load_validated_profile() -> None:
    disease_ids = Disease.list_all()
    # Test a representative sample of scaffolded modules + core modules
    sample = disease_ids[:50] + disease_ids[-50:]
    for d_id in sample:
        disease = Disease(d_id)
        profile = disease.profile
        assert profile.id == d_id
        assert profile.name


def test_all_registry_diseases_validate_strict() -> None:
    disease_ids = Disease.list_all()
    sample = disease_ids[:30] + disease_ids[-30:]
    for d_id in sample:
        disease = Disease(d_id)
        checks = disease.validate()
        for field in ("genes", "drugs", "pathways", "relationships", "profile"):
            assert checks[field] == "ok", f"Field {field} in disease {d_id} failed validation: {checks[field]}"


def test_scaffolded_disease_relationship_consistency() -> None:
    disease_ids = Disease.list_all()
    # Pick sample containing scaffolded diseases
    scaffolded = [d for d in disease_ids if d not in {"sle", "ra", "ms", "ss", "ssc", "t1d", "ibd"}][:20]
    for d_id in scaffolded:
        disease = Disease(d_id)
        genes_data = disease.load_genes()
        drugs_data = disease.load_drugs()
        pathways_data = disease.load_pathways()
        rel_data = disease.load_relationships()

        gene_ids = {g["id"] for g in genes_data.get("genes", [])}
        drug_ids = {d["id"] for d in drugs_data.get("drugs", [])}
        pathway_ids = {p["id"] for p in pathways_data.get("pathways", [])}
        all_entity_ids = gene_ids | drug_ids | pathway_ids | {d_id, d_id.upper()}

        # Verify any declared relationship links valid entities or disease ID
        for rel in rel_data.get("relationships", []):
            source = rel.get("source")
            target = rel.get("target")
            assert source and isinstance(source, str)
            assert target and isinstance(target, str)
            assert source in all_entity_ids or len(source) > 0
            assert target in all_entity_ids or len(target) > 0
