"""Provenance footer tests for priority pipeline HTML report generators."""

from __future__ import annotations

from pathlib import Path

import pytest

from med_research.pipeline.provenance import build_provenance
from med_research.pipeline.reporting import disease_context


@pytest.fixture
def sample_library():
    return [
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
        {
            "id": "belimumab",
            "name": "Belimumab (Benlysta)",
            "type": "Monoclonal Antibody",
            "target": "BAFF (BLyS)",
            "mechanism": "Neutralizes BAFF",
            "category": "Biologic",
            "mw": 147000,
            "logp": -10.0,
            "hbd": 120,
            "hba": 150,
            "rotb": 200,
            "tpsa": 5000,
        },
    ]


def _assert_provenance_footer(html: str, provenance: dict, disease_id: str) -> None:
    fingerprint = provenance["fingerprint"]
    assert len(fingerprint) == 20
    assert fingerprint in html
    assert "Reproducibility" in html
    assert provenance["run_id"] in html
    assert provenance["cache_or_live"] in html

    display_name = disease_context(disease_id)["name"]
    assert display_name in html
    if disease_id != "sle":
        assert display_name != "Lupus"


def _read_report(path: str) -> str:
    report_path = Path(path)
    html = report_path.read_text(encoding="utf-8")
    report_path.unlink(missing_ok=True)
    return html


@pytest.fixture
def minimal_literature_results():
    return {
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


@pytest.fixture
def minimal_literature_entities():
    return {
        "genes": {
            "BTK": {"name": "Bruton Tyrosine Kinase", "id": "BTK", "category": "B Cell Signaling"},
        },
        "drugs": {
            "ibrutinib": {"name": "Ibrutinib", "id": "ibrutinib", "category": "BTK Inhibitor"},
        },
        "pathways": {},
    }


@pytest.fixture
def minimal_ct_results():
    return {
        "trials": [{
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
            "conditions": ["RA"],
            "moa_category": "TNF inhibition",
            "kg_matches": {
                "has_match": False,
                "gene_count": 0,
                "drug_count": 0,
                "genes": [],
                "drugs": [],
            },
        }],
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


def test_drug_repurposing_report_provenance(
    sample_graph, sample_genes, sample_candidates,
):
    from med_research.pipeline.drug_repurposing.engine import (
        identify_untargeted_genes,
        score_candidates,
    )
    from med_research.pipeline.drug_repurposing.report import generate_html_report

    disease_id = "ra"
    untargeted = identify_untargeted_genes(sample_graph)
    untargeted_ids = {gene["id"] for gene in untargeted}
    scored = score_candidates(sample_graph, sample_candidates, sample_genes, disease_id=disease_id)
    scored = [candidate for candidate in scored if candidate["gene_id"] in untargeted_ids]
    provenance = build_provenance(
        disease_id=disease_id,
        module="drug_repurposing",
        sources=["knowledge_graph"],
        cache_or_live="cache",
        scoring={"ranking": "composite_score"},
        run_id="dr-test-run",
    )

    report_path = generate_html_report(
        scored,
        untargeted,
        sample_genes,
        sample_graph,
        disease_id=disease_id,
        provenance=provenance,
    )
    _assert_provenance_footer(_read_report(report_path), provenance, disease_id)


def test_literature_mining_report_provenance(
    minimal_literature_results,
    minimal_literature_entities,
    sample_candidates,
):
    from med_research.pipeline.literature_mining.report import generate_literature_report

    disease_id = "ibd"
    provenance = build_provenance(
        disease_id=disease_id,
        module="literature_mining",
        sources=["pubmed"],
        query="anti-TNF",
        cache_or_live="cache",
        run_id="lit-test-run",
    )

    report_path = generate_literature_report(
        minimal_literature_results,
        minimal_literature_entities,
        sample_candidates,
        disease_id=disease_id,
        provenance=provenance,
    )
    _assert_provenance_footer(_read_report(report_path), provenance, disease_id)


def test_bioinformatics_report_provenance():
    from med_research.pipeline.bioinformatics.report import generate_bioinformatics_report

    disease_id = "ra"
    enrichment_results = {
        "GO_Biological_Process_2023": {
            "library": "GO_Biological_Process_2023",
            "terms": [{
                "term": "immune response",
                "adj_p_value": 0.01,
                "genes": ["TNF"],
                "odds_ratio": 4.0,
            }],
            "total_significant": 1,
        },
    }
    gene_list = [
        {"gene_id": "TNF", "symbol": "TNF", "name": "Tumor Necrosis Factor", "category": "Cytokine"},
    ]
    provenance = build_provenance(
        disease_id=disease_id,
        module="bioinformatics",
        sources=["enrichr"],
        cache_or_live="cache",
        scoring={"analysis": "pathway_enrichment"},
        run_id="bio-test-run",
    )

    report_path = generate_bioinformatics_report(
        enrichment_results,
        gene_list,
        disease_id=disease_id,
        provenance=provenance,
    )
    _assert_provenance_footer(_read_report(report_path), provenance, disease_id)


def test_virtual_screening_report_provenance(sample_library):
    from med_research.pipeline.virtual_screening.report import generate_screening_report
    from med_research.pipeline.virtual_screening.screening import screen_compounds

    disease_id = "ra"
    results = screen_compounds(
        target_genes=["BTK"],
        compound_library=sample_library,
        top_n=3,
        disease_id=disease_id,
    )
    provenance = build_provenance(
        disease_id=disease_id,
        module="virtual_screening",
        sources=["knowledge_graph"],
        cache_or_live="cache",
        scoring={
            "strategy_id": results.get("strategy_id", ""),
            "strategy_fingerprint": results.get("strategy_fingerprint", ""),
        },
        run_id="vs-test-run",
    )

    report_path = generate_screening_report(
        results,
        disease_id=disease_id,
        provenance=provenance,
    )
    _assert_provenance_footer(_read_report(report_path), provenance, disease_id)


def test_adverse_events_report_provenance():
    from med_research.pipeline.adverse_events.profiler import compute_adverse_event_score
    from med_research.pipeline.adverse_events.report import generate_html_report

    disease_id = "ibd"
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
    provenance = build_provenance(
        disease_id=disease_id,
        module="adverse_events",
        sources=["fda_labels"],
        cache_or_live="cache",
        run_id="ae-test-run",
    )

    report_path = generate_html_report(
        results,
        disease_id=disease_id,
        provenance=provenance,
    )
    _assert_provenance_footer(_read_report(report_path), provenance, disease_id)


def test_clinical_trials_report_provenance(minimal_ct_results):
    from med_research.pipeline.clinical_trials.report import generate_ct_report

    disease_id = "ra"
    provenance = build_provenance(
        disease_id=disease_id,
        module="clinical_trials",
        sources=["clinicaltrials_gov"],
        query="rheumatoid arthritis",
        cache_or_live="cache",
        run_id="ct-test-run",
    )

    report_path = generate_ct_report(
        minimal_ct_results,
        disease_id=disease_id,
        provenance=provenance,
    )
    _assert_provenance_footer(_read_report(report_path), provenance, disease_id)


def test_car_t_predictor_report_provenance():
    from med_research.pipeline.car_t_predictor.predictor import compute_all_scores
    from med_research.pipeline.car_t_predictor.report import generate_html_report

    disease_id = "ra"
    results = compute_all_scores(disease_id=disease_id)
    assert results, "CAR-T scoring should return results for RA"
    provenance = build_provenance(
        disease_id=disease_id,
        module="car_t_predictor",
        sources=["knowledge_graph"],
        cache_or_live="cache",
        scoring={"ranking": "car_t_heuristic"},
        run_id="cart-test-run",
    )

    report_path = generate_html_report(
        results,
        disease_id=disease_id,
        provenance=provenance,
    )
    _assert_provenance_footer(_read_report(report_path), provenance, disease_id)


def test_biomarker_discovery_report_provenance():
    from med_research.pipeline.biomarker_discovery.discover import compute_biomarker_matrix
    from med_research.pipeline.biomarker_discovery.report import generate_html_report

    disease_id = "ibd"
    results = compute_biomarker_matrix(disease_id=disease_id, save=False)
    assert results, "Biomarker matrix should return results for IBD"
    provenance = build_provenance(
        disease_id=disease_id,
        module="biomarker_discovery",
        sources=["knowledge_graph"],
        cache_or_live="cache",
        run_id="bm-test-run",
    )

    report_path = generate_html_report(
        results,
        disease_id=disease_id,
        provenance=provenance,
    )
    _assert_provenance_footer(_read_report(report_path), provenance, disease_id)
