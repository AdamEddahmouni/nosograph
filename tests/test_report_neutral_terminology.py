"""Report HTML should not leak unrelated SLE/lupus labels for non-SLE diseases."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from med_research.pipeline.reporting import disease_context

UNRELATED_TERMS = re.compile(r"\b(?:lupus|sle|systemic lupus erythematosus)\b", re.IGNORECASE)

pytestmark = pytest.mark.unit




def _visible_text(html: str) -> str:
    """Strip tags/scripts so we only inspect user-visible copy."""
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text)


def _disease_labels(disease_id: str) -> set[str]:
    context = disease_context(disease_id)
    return {
        context["name"],
        context["profile_name"],
        context["short_label"],
        context["name"].split("(")[0].strip(),
    }


@pytest.mark.parametrize("disease_id", ["ra", "ibd"])
def test_drug_synergy_report_avoids_unrelated_lupus_copy(disease_id):
    from med_research.pipeline.drug_synergy.engine import compute_synergy
    from med_research.pipeline.drug_synergy.report import generate_html_report

    pairs = compute_synergy(disease_id=disease_id, save=False)
    assert pairs
    report_path = generate_html_report(pairs[:5], disease_id=disease_id)
    html = Path(report_path).read_text(encoding="utf-8")
    visible = _visible_text(html)
    assert any(label in visible for label in _disease_labels(disease_id) if label)
    assert not UNRELATED_TERMS.search(visible), visible


@pytest.mark.parametrize("disease_id", ["ra", "ibd", "ms", "ss", "ssc", "t1d"])
def test_gene_expression_report_avoids_unrelated_lupus_copy(disease_id):
    from med_research.pipeline.gene_expression.correlator import compute_all_correlations
    from med_research.pipeline.gene_expression.report import generate_html_report

    results = compute_all_correlations(disease_id=disease_id, save=False)
    assert results
    report_path = generate_html_report(results[:5], disease_id=disease_id)
    html = Path(report_path).read_text(encoding="utf-8")
    visible = _visible_text(html)
    assert any(label in visible for label in _disease_labels(disease_id) if label)
    assert not UNRELATED_TERMS.search(visible), visible


@pytest.mark.parametrize("disease_id", ["ra", "ibd"])
def test_network_pharmacology_report_avoids_unrelated_lupus_copy(disease_id):
    from med_research.pipeline.network_pharmacology.analyzer import compute_all_metrics
    from med_research.pipeline.network_pharmacology.report import generate_html_report

    results = compute_all_metrics(disease_id=disease_id)
    assert results.get("status") != "blocked"
    assert "graph_metrics" in results
    report_path = generate_html_report(results, disease_id=disease_id)
    html = Path(report_path).read_text(encoding="utf-8")
    visible = _visible_text(html)
    assert any(label in visible for label in _disease_labels(disease_id) if label)
    assert not UNRELATED_TERMS.search(visible), visible


@pytest.mark.parametrize("disease_id", ["ra", "ibd"])
def test_ml_predictor_report_avoids_unrelated_lupus_copy(disease_id):
    pytest.importorskip("sklearn")
    pytest.importorskip("xgboost")
    from med_research.pipeline.knowledge_graph.builder import build_graph
    from med_research.pipeline.ml_predictor.predictor import train_and_predict
    from med_research.pipeline.ml_predictor.report import generate_ml_report

    graph = build_graph(disease_id)
    results = train_and_predict(graph, top_n=10)
    assert results.get("top_untargeted")
    report_path = generate_ml_report(results, disease_id=disease_id)
    html = Path(report_path).read_text(encoding="utf-8")
    visible = _visible_text(html)
    assert any(label in visible for label in _disease_labels(disease_id) if label)
    assert not UNRELATED_TERMS.search(visible), visible


@pytest.mark.parametrize("disease_id", ["ra", "ibd"])
def test_semantic_search_report_avoids_unrelated_lupus_copy(disease_id):
    from med_research.pipeline.semantic_search.engine import SemanticSearchEngine
    from med_research.pipeline.semantic_search.report import generate_semantic_report

    engine = SemanticSearchEngine(disease_id=disease_id)
    results = engine.search("anti-TNF therapy", top_k=5)
    indexed_count = engine.get_indexed_count()
    report_path = generate_semantic_report(
        results,
        "anti-TNF therapy",
        indexed_count,
        disease_id=disease_id,
    )
    html = Path(report_path).read_text(encoding="utf-8")
    visible = _visible_text(html)
    assert any(label in visible for label in _disease_labels(disease_id) if label)
    assert not UNRELATED_TERMS.search(visible), visible


@pytest.mark.parametrize("disease_id", ["ra", "ibd"])
def test_evidence_gatherer_report_avoids_unrelated_lupus_copy(disease_id):
    from med_research.pipeline.evidence.gatherer_report import generate_html_report
    from med_research.pipeline.provenance import build_provenance

    gathered = {
        "query": f"{disease_id} treatment",
        "total_results": 1,
        "elapsed_seconds": 0.5,
        "results_by_source": {"pubmed": 1},
        "all_results": [
            {
                "source_type": "pubmed",
                "title": f"Novel therapy in {disease_id}",
                "year": "2024",
                "snippet": "Clinical outcomes",
                "url": "https://example.com/1",
            }
        ],
        "crossref": {"pairs": []},
    }
    provenance = build_provenance(
        disease_id=disease_id,
        module="evidence_gather",
        sources=["pubmed"],
        query=gathered["query"],
        cache_or_live="cache",
    )
    report_path = generate_html_report(gathered, provenance=provenance)
    html = Path(report_path).read_text(encoding="utf-8")
    visible = _visible_text(html)
    assert not UNRELATED_TERMS.search(visible), visible


@pytest.mark.parametrize("disease_id", ["ra", "ibd"])
def test_llm_extractor_report_avoids_unrelated_lupus_copy(disease_id):
    from med_research.pipeline.evidence.extractor_report import generate_html_report
    from med_research.pipeline.provenance import build_provenance

    results = {
        "query": f"{disease_id} biologic therapy",
        "model": "gpt-4o-mini",
        "total_extracted": 1,
        "successful_extractions": 1,
        "elapsed_seconds": 1.0,
        "extractions": [
            {
                "title": f"Biologic therapy in {disease_id}",
                "year": "2024",
                "source_type": "pubmed",
                "source": "PMID:123",
                "evidence_level": "rct",
                "model_system": "human",
                "key_findings": "Improved outcomes",
                "drugs_mentioned": ["adalimumab"],
                "confidence": 80,
                "relevance_to_query": 85,
            }
        ],
        "stats": {
            "evidence_levels": {"rct": 1},
            "model_systems": {"human": 1},
            "study_designs": {"rct": 1},
            "unique_drugs_mentioned": ["adalimumab"],
            "avg_confidence": 80.0,
            "n_unique_drugs": 1,
        },
    }
    provenance = build_provenance(
        disease_id=disease_id,
        module="llm_extractor",
        sources=["pubmed"],
        query=results["query"],
        cache_or_live="cache",
        model="gpt-4o-mini",
    )
    report_path = generate_html_report(results, provenance=provenance)
    html = Path(report_path).read_text(encoding="utf-8")
    visible = _visible_text(html)
    assert not UNRELATED_TERMS.search(visible), visible


@pytest.mark.parametrize("disease_id", ["ra", "ibd"])
def test_evidence_monitor_report_avoids_unrelated_lupus_copy(disease_id):
    from med_research.pipeline.evidence.monitor_report import generate_html_report
    from med_research.pipeline.provenance import build_provenance

    prev_snapshot = {
        "snapshot_id": "20250101_120000",
        "queries": {f"{disease_id} treatment": {"total": 1}},
        "drugs": {},
        "genes": {},
    }
    curr_snapshot = {
        "snapshot_id": "20250102_120000",
        "queries": {f"{disease_id} treatment": {"total": 2}},
        "drugs": {},
        "genes": {},
    }
    diff = {
        "prev_snapshot": prev_snapshot["snapshot_id"],
        "curr_snapshot": curr_snapshot["snapshot_id"],
        "hours_elapsed": 24.0,
        "total_changes": 1,
        "alerts": [],
        "changes": {
            "changed_queries": [f"{disease_id} treatment"],
            "changed_drugs": [],
            "changed_genes": [],
        },
    }
    provenance = build_provenance(
        disease_id=disease_id,
        module="evidence_monitor",
        sources=["pubmed"],
        cache_or_live="cache",
    )
    report_path = generate_html_report(
        diff,
        prev_snapshot,
        curr_snapshot,
        provenance=provenance,
    )
    html = Path(report_path).read_text(encoding="utf-8")
    visible = _visible_text(html)
    assert not UNRELATED_TERMS.search(visible), visible


@pytest.mark.parametrize("disease_id", ["ra", "ibd"])
def test_drug_repurposing_report_avoids_unrelated_lupus_copy(
    disease_id,
    sample_graph,
    sample_genes,
    sample_candidates,
):
    from med_research.pipeline.drug_repurposing.engine import (
        identify_untargeted_genes,
        score_candidates,
    )
    from med_research.pipeline.drug_repurposing.report import generate_html_report

    untargeted = identify_untargeted_genes(sample_graph, disease_id=disease_id)
    untargeted_ids = {gene["id"] for gene in untargeted}
    scored = score_candidates(
        sample_graph,
        sample_candidates,
        sample_genes,
        disease_id=disease_id,
    )
    scored = [candidate for candidate in scored if candidate["gene_id"] in untargeted_ids]
    assert scored
    report_path = generate_html_report(
        scored[:5],
        untargeted,
        sample_genes,
        sample_graph,
        disease_id=disease_id,
    )
    html = Path(report_path).read_text(encoding="utf-8")
    visible = _visible_text(html)
    assert any(label in visible for label in _disease_labels(disease_id) if label)
    assert not UNRELATED_TERMS.search(visible), visible


@pytest.mark.parametrize("disease_id", ["ra", "ibd"])
def test_bioinformatics_report_avoids_unrelated_lupus_copy(disease_id):
    from med_research.pipeline.bioinformatics.report import generate_bioinformatics_report

    enrichment_results = {
        "GO_Biological_Process_2023": {
            "library": "GO_Biological_Process_2023",
            "terms": [
                {
                    "term": "immune response",
                    "adj_p_value": 0.01,
                    "genes": ["TNF"],
                    "odds_ratio": 4.0,
                }
            ],
            "total_significant": 1,
        },
    }
    gene_list = [
        {
            "gene_id": "TNF",
            "symbol": "TNF",
            "name": "Tumor Necrosis Factor",
            "category": "Cytokine",
        },
    ]
    hub_scores = [
        {
            "symbol": "TNF",
            "hub_score": 0.12,
            "is_lupus_gene": True,
            "degree": 8,
            "betweenness_centrality": 0.04,
            "gene_id": "TNF",
        }
    ]
    ppi_crossref = {
        "hub_candidate_matches": [],
        "hub_untargeted": [],
        "n_validated": 0,
        "n_novel": 0,
    }
    ppi_graph = {
        "nodes": [
            {"id": "TNF", "symbol": "TNF", "is_seed": True, "is_lupus_gene": True},
            {"id": "IL6", "symbol": "IL6", "is_seed": False},
        ],
        "edges": [{"source": "TNF", "target": "IL6", "score": 0.85}],
    }
    gwas_results = {
        "snp_data": [
            {
                "chromosome": "6",
                "position": 100000,
                "p_value": 1e-8,
                "rsid": "rs123456",
            }
        ],
    }
    gwas_crossref = {
        "validated": {},
        "novel": {},
        "missing": {},
        "n_validated": 0,
        "n_novel": 0,
    }
    report_path = generate_bioinformatics_report(
        enrichment_results,
        gene_list,
        hub_scores=hub_scores,
        ppi_crossref=ppi_crossref,
        ppi_graph=ppi_graph,
        gwas_results=gwas_results,
        gwas_crossref=gwas_crossref,
        disease_id=disease_id,
    )
    html = Path(report_path).read_text(encoding="utf-8")
    visible = _visible_text(html)
    assert any(label in visible for label in _disease_labels(disease_id) if label)
    assert not UNRELATED_TERMS.search(visible), visible


@pytest.mark.parametrize("disease_id", ["ra", "ibd"])
def test_literature_mining_report_avoids_unrelated_lupus_copy(
    disease_id,
    sample_candidates,
):
    from med_research.pipeline.literature_mining.report import generate_literature_report

    results = {
        "stats": {
            "total_articles": 2,
            "articles_with_matches": 1,
            "genes_found": 1,
            "drugs_found": 1,
            "candidates_supported": 1,
            "spacy_ner": "regex-based (no spaCy)",
            "novel_entities_found": 0,
            "statistics_mentions": 0,
        },
        "candidate_support": {
            "c001": [{"pmid": "12345", "title": "BTK study", "year": "2024"}],
        },
        "gene_coverage": {"BTK": {"articles": 1, "pmids": ["12345"]}},
        "drug_coverage": {},
        "novel_entities": {},
        "article_matches": [],
    }
    entities = {
        "genes": {
            "BTK": {"name": "Bruton Tyrosine Kinase", "id": "BTK", "category": "B Cell Signaling"},
        },
        "drugs": {
            "ibrutinib": {"name": "Ibrutinib", "id": "ibrutinib", "category": "BTK Inhibitor"},
        },
        "pathways": {},
    }
    report_path = generate_literature_report(
        results,
        entities,
        sample_candidates,
        disease_id=disease_id,
    )
    html = Path(report_path).read_text(encoding="utf-8")
    visible = _visible_text(html)
    assert any(label in visible for label in _disease_labels(disease_id) if label)
    assert not UNRELATED_TERMS.search(visible), visible


@pytest.mark.parametrize("disease_id", ["ra", "ibd"])
def test_clinical_trials_report_avoids_unrelated_lupus_copy(disease_id):
    from med_research.pipeline.clinical_trials.report import generate_ct_report

    results = {
        "trials": [
            {
                "nct_id": "NCT00000001",
                "title": "Anti-TNF trial",
                "summary": "Trial summary",
                "status": "RECRUITING",
                "phases": ["PHASE3"],
                "primary_phase": "PHASE3",
                "phase_label": "Phase 3",
                "interventions": ["Adalimumab"],
                "intervention_types": ["DRUG"],
                "sponsor_name": "Sponsor",
                "sponsor_class": "INDUSTRY",
                "enrollment": 100,
                "start_date": "2024-01-01",
                "completion_date": "2026-01-01",
                "why_stopped": "",
                "conditions": [disease_id.upper()],
                "moa_category": "TNF inhibition",
                "kg_matches": {
                    "has_match": False,
                    "gene_count": 0,
                    "drug_count": 0,
                    "genes": [],
                    "drugs": [],
                },
            }
        ],
        "stats": {
            "total_trials": 1,
            "kg_matched_trials": 0,
            "total_enrollment": 100,
            "avg_enrollment": 100,
            "statuses": {"RECRUITING": 1},
            "phases": {"Phase 3": 1},
            "moas": {"TNF inhibition": 1},
            "top_sponsors": {"Sponsor": 1},
        },
        "kg_crossref": {
            "gene_hits": {},
            "drug_hits": {},
            "trials_with_matches": [],
            "total_matched": 0,
        },
    }
    report_path = generate_ct_report(results, disease_id=disease_id)
    html = Path(report_path).read_text(encoding="utf-8")
    visible = _visible_text(html)
    assert any(label in visible for label in _disease_labels(disease_id) if label)
    assert not UNRELATED_TERMS.search(visible), visible


@pytest.mark.parametrize("disease_id", ["ra", "ibd"])
def test_virtual_screening_report_avoids_unrelated_lupus_copy(disease_id):
    from med_research.pipeline.virtual_screening.report import generate_screening_report
    from med_research.pipeline.virtual_screening.screening import screen_compounds

    library = [
        {
            "id": "baricitinib",
            "name": "Baricitinib (Olumiant)",
            "type": "Small Molecule",
            "target": "JAK1/JAK2",
            "mechanism": "JAK1/2 inhibitor",
            "category": "JAK Inhibitor",
            "mw": 371,
            "logp": 1.7,
            "hbd": 2,
            "hba": 7,
            "rotb": 5,
            "tpsa": 112,
        },
    ]
    results = screen_compounds(
        target_genes=["BTK"],
        compound_library=library,
        top_n=3,
        disease_id=disease_id,
    )
    assert results.get("status") != "blocked"
    report_path = generate_screening_report(results, disease_id=disease_id)
    html = Path(report_path).read_text(encoding="utf-8")
    visible = _visible_text(html)
    assert any(label in visible for label in _disease_labels(disease_id) if label)
    assert not UNRELATED_TERMS.search(visible), visible


@pytest.mark.parametrize("disease_id", ["ra", "ibd"])
def test_adverse_events_report_avoids_unrelated_lupus_copy(disease_id):
    from med_research.pipeline.adverse_events.profiler import compute_adverse_event_score
    from med_research.pipeline.adverse_events.report import generate_html_report

    profile = {
        "drug_id": "adalimumab",
        "drug_name": "Adalimumab",
        "common_ae": ["headache"],
        "severe_ae": [],
        "lupus_overlap_ae": [],
        "severity_burden": 3,
        "chronic_use_safety": 7,
        "dil_risk": 0,
        "black_box_warnings": [],
    }
    results = [compute_adverse_event_score(profile, disease_id=disease_id)]
    report_path = generate_html_report(results, disease_id=disease_id)
    html = Path(report_path).read_text(encoding="utf-8")
    visible = _visible_text(html)
    assert any(label in visible for label in _disease_labels(disease_id) if label)
    assert not UNRELATED_TERMS.search(visible), visible


@pytest.mark.parametrize("disease_id", ["ra", "ibd"])
def test_car_t_predictor_report_avoids_unrelated_lupus_copy(disease_id):
    from med_research.pipeline.car_t_predictor.predictor import compute_all_scores
    from med_research.pipeline.car_t_predictor.report import generate_html_report

    results = compute_all_scores(disease_id=disease_id)
    assert results
    report_path = generate_html_report(results, disease_id=disease_id)
    html = Path(report_path).read_text(encoding="utf-8")
    visible = _visible_text(html)
    assert any(label in visible for label in _disease_labels(disease_id) if label)
    assert not UNRELATED_TERMS.search(visible), visible


@pytest.mark.parametrize("disease_id", ["ra", "ibd"])
def test_biomarker_discovery_report_avoids_unrelated_lupus_copy(disease_id):
    from med_research.pipeline.biomarker_discovery.discover import compute_biomarker_matrix
    from med_research.pipeline.biomarker_discovery.report import generate_html_report

    results = compute_biomarker_matrix(disease_id=disease_id, save=False)
    assert results
    report_path = generate_html_report(results, disease_id=disease_id)
    html = Path(report_path).read_text(encoding="utf-8")
    visible = _visible_text(html)
    assert any(label in visible for label in _disease_labels(disease_id) if label)
    assert not UNRELATED_TERMS.search(visible), visible


def test_cross_disease_report_includes_multi_disease_labels():
    """Cross-disease report lists all diseases; RA and IBD labels must appear."""
    from med_research.pipeline.cross_disease.analyzer import compute_cross_disease_analysis
    from med_research.pipeline.cross_disease.report import generate_html_report

    results = compute_cross_disease_analysis()
    report_path = generate_html_report(results)
    html = Path(report_path).read_text(encoding="utf-8")
    visible = _visible_text(html)
    assert "Rheumatoid Arthritis" in visible
    assert any(label in visible for label in _disease_labels("ibd") if label)
