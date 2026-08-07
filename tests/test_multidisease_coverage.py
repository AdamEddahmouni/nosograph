"""Strict multi-disease coverage contract tests."""

import pytest

DISEASES = ["sle", "ra", "ms", "ss", "ssc", "t1d", "ibd"]


@pytest.mark.parametrize("disease_id", DISEASES)
def test_core_coverage_reports_all_five_data_files(disease_id):
    from med_research.diseases.coverage import coverage_for_disease

    coverage = coverage_for_disease(disease_id)
    assert coverage.level == "full"
    assert coverage.status == "ready"
    assert set(coverage.curated_inputs) >= {
        "profile", "genes", "drugs", "pathways", "relationships"
    }
    assert coverage.missing_inputs == []


@pytest.mark.parametrize("disease_id", DISEASES)
def test_all_disease_graphs_build_and_relationships_are_present(disease_id):
    from med_research.diseases.base import Disease
    from med_research.pipeline.knowledge_graph.builder import build_graph

    disease = Disease(disease_id)
    relationships = disease.load_relationships()["relationships"]
    graph = build_graph(disease_id)

    assert relationships
    assert graph.number_of_nodes() > 0
    assert graph.number_of_edges() >= len(relationships)


@pytest.mark.parametrize("disease_id", DISEASES)
def test_relationships_reference_known_nodes(disease_id):
    from med_research.diseases.base import Disease

    disease = Disease(disease_id)
    genes = {g["id"] for g in disease.load_genes()["genes"]}
    drugs = {d["id"] for d in disease.load_drugs()["drugs"]}
    pathways = {p["id"] for p in disease.load_pathways()["pathways"]}
    valid = genes | drugs | pathways | {disease.profile.kg_node_id, disease.profile.name}
    for rel in disease.load_relationships()["relationships"]:
        assert rel["source"] in valid and rel["target"] in valid


def test_missing_required_config_is_blocked(monkeypatch):
    from med_research.diseases.base import Disease
    from med_research.diseases.coverage import module_coverage

    monkeypatch.setattr(Disease, "config", property(lambda self: {}))
    result = module_coverage("ra", "car_t", ("genes", "car_t_scores"))
    assert result.level == "unsupported"
    assert result.status == "blocked"
    assert "car_t_scores" in result.missing_inputs
    assert result.to_dict()["module"] == "car_t"


def test_known_disease_queries_never_inherit_sle_terms():
    from med_research.pipeline.bioinformatics.gwas import disease_search_terms
    from med_research.pipeline.literature_mining.miner import _disease_queries

    literature = _disease_queries("ra")
    gwas = disease_search_terms("ibd")
    assert literature and gwas
    assert all("lupus" not in query.lower() for query in literature)
    assert all("lupus" not in term.lower() for term in gwas)
    assert any("rheumatoid" in query.lower() or "ra[" in query.lower() for query in literature)
    assert any("bowel" in term.lower() or "crohn" in term.lower() for term in gwas)


def test_missing_known_disease_literature_config_is_empty_not_sle(monkeypatch):
    from med_research.diseases.base import Disease
    from med_research.pipeline.literature_mining.miner import _disease_queries

    monkeypatch.setattr(Disease, "config", property(lambda self: {}))
    assert _disease_queries("ra") == []


def test_disease_neutral_risk_accessor_preserves_legacy_configs():
    from med_research.diseases.base import Disease

    for disease_id in DISEASES:
        disease = Disease(disease_id)
        assert disease.get_disease_risk_config() == disease.get_drug_induced_lupus_risk()
        assert disease.get_disease_risk_config()


def test_api_models_accept_coverage_metadata():
    from med_research.web.models import DiseaseInfo
    from med_research.web.models.shared import LiteratureResponse, ScreeningResponse

    disease = DiseaseInfo(id="ibd", name="IBD", coverage={"level": "full"})
    assert disease.coverage["level"] == "full"
    literature = LiteratureResponse(
        total_articles=0,
        queries_run=0,
        articles=[],
        gene_coverage=[],
        coverage={"level": "unsupported", "status": "blocked"},
    )
    screening = ScreeningResponse(
        targets=[],
        compounds_screened=0,
        total_pairings=0,
        tier1_count=0,
        tier2_count=0,
        vina_available=False,
        rdkit_available=False,
        coverage={"level": "full", "status": "ready"},
    )
    assert literature.coverage["status"] == "blocked"
    assert screening.coverage["level"] == "full"


def test_unknown_disease_coverage_is_structured_as_blocked():
    from med_research.diseases.coverage import coverage_for_disease, module_coverage

    core = coverage_for_disease("not-a-disease")
    module = module_coverage("not-a-disease", "gwas", ("genes",))
    assert core.status == "blocked"
    assert module.status == "blocked"
    assert module.missing_inputs == ["disease"]


def test_single_drug_safety_result_keeps_coverage_metadata():
    from med_research.pipeline.adverse_events.profiler import get_drug_profile

    result = get_drug_profile("belimumab", disease_id="sle")
    assert result["status"] == "ready"
    assert result["coverage"]["module"] == "safety"


def test_dashboard_has_coverage_rendering_and_blocks_direct_results():
    from pathlib import Path

    root = Path(__file__).parents[1] / "src/med_research/web/static"
    script = (root / "js/dashboard.js").read_text(encoding="utf-8")
    styles = (root / "css/dashboard.css").read_text(encoding="utf-8")
    assert "renderCoverageBadge" in script
    assert "Unsupported for this disease" in script
    assert "limited_coverage" in script
    assert ".coverage-badge" in styles
    for renderer in ("renderKGResult", "renderRepurposeResult", "renderBiomarkerResult", "renderSemanticResult", "renderEvidenceResult"):
        start = script.index(f"function {renderer}")
        end = script.find("\nfunction ", start + 10)
        body = script[start:] if end == -1 else script[start:end]
        assert "coverage?.status === 'blocked'" in body
