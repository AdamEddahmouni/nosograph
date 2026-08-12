

"""Contract tests for scientifically reliable multi-disease execution."""

import pytest

DISEASES = ["sle", "ra", "ms", "ss", "ssc", "t1d", "ibd"]

pytestmark = pytest.mark.unit




@pytest.mark.parametrize("disease_id", DISEASES)
def test_every_disease_has_complete_research_contract(disease_id):
    from med_research.diseases.base import Disease

    disease = Disease(disease_id)
    checks = disease.validate()

    assert all(status == "ok" for status in checks.values()), checks
    assert disease.get_display_name()
    assert disease.get_drug_target_exclusions() is not None
    assert disease.get_pathway_keywords()
    assert disease.get_trial_query()
    assert disease.get_gwas_search_terms()


@pytest.mark.parametrize("disease_id", DISEASES)
def test_core_entity_loaders_are_disease_specific(disease_id):
    from med_research.pipeline.bioinformatics.enrichment import get_disease_gene_list, load_kg_genes

    genes = load_kg_genes(disease_id)
    result = get_disease_gene_list(genes, disease_id=disease_id)

    assert result
    assert {item["gene_id"] for item in result} <= set(genes)
    assert all("disease_evidence" in item for item in result)


def test_gwas_missing_gene_filter_uses_requested_disease_exclusions():
    from med_research.pipeline.bioinformatics.gwas import cross_reference_with_kg

    gwas = {"gene_associations": {}, "total_studies_analyzed": 0, "total_associations": 0}
    genes = {"CD20": {"id": "CD20", "name": "CD20"}, "TNF": {"id": "TNF", "name": "TNF"}}

    sle = cross_reference_with_kg(gwas, genes, disease_id="sle")
    ra = cross_reference_with_kg(gwas, genes, disease_id="ra")

    assert "CD20" not in sle["missing"]
    assert "CD20" in ra["missing"]


def test_clinical_trial_entity_loading_is_disease_specific(monkeypatch):
    from med_research.pipeline.clinical_trials import tracker

    monkeypatch.setattr(
        tracker,
        "config_load_genes",
        lambda disease_id="sle": {
            "genes": [{"id": disease_id, "name": disease_id, "category": ""}]
        },
    )
    monkeypatch.setattr(
        tracker,
        "config_load_drugs",
        lambda disease_id="sle": {"drugs": [{"id": disease_id, "name": disease_id, "target": ""}]},
    )

    entities = tracker.load_kg_entities("ra")
    assert set(entities["genes"]) == {"ra"}
    assert set(entities["drugs"]) == {"ra"}


def test_non_sle_safety_uses_active_disease_symptoms():
    from med_research.pipeline.adverse_events import profiler

    profile = {
        "drug_id": "fixture",
        "drug_name": "Fixture",
        "common_ae": ["diarrhea", "abdominal pain"],
        "severe_ae": [],
        "lupus_overlap_ae": [],
        "severity_burden": 1,
        "chronic_use_safety": 8,
        "dil_risk": 0,
    }
    result = profiler.compute_adverse_event_score(profile, disease_id="ibd")

    assert result["disease_id"] == "ibd"
    assert result["n_disease_overlap_ae"] >= 2
    assert result["disease_symptom_overlap_score"] < 10


def test_non_sle_carscores_are_not_silent_sle_fallback():
    from med_research.pipeline.car_t_predictor.predictor import compute_all_scores

    sle = {item["gene_id"]: item for item in compute_all_scores(disease_id="sle")}
    ibd = {item["gene_id"]: item for item in compute_all_scores(disease_id="ibd")}

    shared = set(sle) & set(ibd)
    assert shared
    assert any(sle[gene]["composite_score"] != ibd[gene]["composite_score"] for gene in shared)
    assert all(item["disease_id"] == "ibd" for item in ibd.values())
