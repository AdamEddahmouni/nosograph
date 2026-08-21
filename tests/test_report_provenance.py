"""Provenance footer tests for priority pipeline HTML report generators."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from med_research.pipeline.provenance import build_provenance
from med_research.pipeline.reporting import disease_context

PROJECT_ROOT = Path(__file__).parent.parent

pytestmark = pytest.mark.unit


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


def _assert_provenance_footer(html: str, provenance: dict, disease_id: str | None = None) -> None:
    fingerprint = provenance["fingerprint"]
    assert len(fingerprint) == 20
    assert fingerprint in html
    assert "Reproducibility" in html
    assert provenance["run_id"] in html
    assert provenance["cache_or_live"] in html

    if not disease_id or disease_id == "multi":
        return

    context = disease_context(disease_id)
    label_candidates = {
        context["name"],
        context["profile_name"],
        context["short_label"],
        context["name"].split("(")[0].strip(),
    }
    if disease_id != "sle":
        assert context["name"] != "Lupus"
    assert any(label and label in html for label in label_candidates), (
        f"Expected a disease label from {label_candidates} in report HTML"
    )


def _read_report(path: str) -> str:
    report_path = Path(path)
    html = report_path.read_text(encoding="utf-8")
    report_path.unlink(missing_ok=True)
    return html


def _assert_cli_provenance_footer(html: str) -> None:
    """Assert CLI --export-html reports include a reproducibility footer."""
    assert "Reproducibility" in html
    assert re.search(r"fingerprint <code>[a-f0-9]{20}</code>", html)
    assert re.search(r"mode (cache|live)", html)
    assert re.search(r"run <code>[^<]+</code>", html)


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
                "conditions": ["RA"],
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


def test_drug_repurposing_report_provenance(
    sample_graph,
    sample_genes,
    sample_candidates,
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


def test_cross_disease_report_provenance(cross_disease_analysis):
    from med_research.pipeline.cross_disease.report import generate_html_report

    results = cross_disease_analysis
    provenance = build_provenance(
        disease_id="multi",
        module="cross_disease",
        sources=["knowledge_graph"],
        cache_or_live="cache",
        run_id="cd-test-run",
    )

    report_path = generate_html_report(results, provenance=provenance)
    html = _read_report(report_path)
    _assert_provenance_footer(html, provenance)
    assert "Rheumatoid Arthritis" in html


def test_drug_synergy_report_provenance(synergy_pairs):
    from med_research.pipeline.drug_synergy.report import generate_html_report

    disease_id = "ra"
    pairs = synergy_pairs
    assert pairs, "Synergy scoring should return results for RA"
    provenance = build_provenance(
        disease_id=disease_id,
        module="drug_synergy",
        sources=["knowledge_graph"],
        cache_or_live="cache",
        run_id="ds-test-run",
    )

    report_path = generate_html_report(pairs, disease_id=disease_id, provenance=provenance)
    _assert_provenance_footer(_read_report(report_path), provenance, disease_id)


def test_network_pharmacology_report_provenance():
    from med_research.pipeline.network_pharmacology.analyzer import compute_all_metrics
    from med_research.pipeline.network_pharmacology.report import generate_html_report

    disease_id = "ibd"
    results = compute_all_metrics(disease_id=disease_id)
    provenance = build_provenance(
        disease_id=disease_id,
        module="network_pharmacology",
        sources=["knowledge_graph"],
        cache_or_live="cache",
        run_id="np-test-run",
    )

    report_path = generate_html_report(results, disease_id=disease_id, provenance=provenance)
    _assert_provenance_footer(_read_report(report_path), provenance, disease_id)


def test_gene_expression_report_provenance(expression_results):
    from med_research.pipeline.gene_expression.report import generate_html_report

    disease_id = "ra"
    results = expression_results
    assert results, "Expression correlation should return results for RA"
    provenance = build_provenance(
        disease_id=disease_id,
        module="gene_expression",
        sources=["curated_literature"],
        cache_or_live="cache",
        run_id="ge-test-run",
    )

    report_path = generate_html_report(
        results,
        disease_id=disease_id,
        provenance=provenance,
    )
    _assert_provenance_footer(_read_report(report_path), provenance, disease_id)


def test_ml_predictor_report_provenance():
    from med_research.pipeline.ml_predictor.report import generate_ml_report

    disease_id = "ibd"
    results = {
        "model_metrics": {
            "n_genes": 40,
            "n_targeted": 10,
            "n_untargeted": 30,
            "cv_roc_auc_mean": 0.82,
        },
        "top_untargeted": [
            {
                "gene_id": "TNF",
                "gene_name": "Tumor Necrosis Factor",
                "category": "Cytokine",
                "druggability_score": 0.88,
                "odds_ratio": 2.1,
                "degree": 6,
            }
        ],
        "feature_importance": {"degree": 0.25, "odds_ratio": 0.20},
        "shap_summary": [{"feature": "degree", "mean_abs_shap": 0.12}],
    }
    provenance = build_provenance(
        disease_id=disease_id,
        module="ml_predictor",
        sources=["knowledge_graph"],
        cache_or_live="cache",
        run_id="ml-test-run",
    )

    report_path = generate_ml_report(results, disease_id=disease_id, provenance=provenance)
    _assert_provenance_footer(_read_report(report_path), provenance, disease_id)


def test_semantic_search_report_provenance():
    from med_research.pipeline.semantic_search.report import generate_semantic_report

    disease_id = "ra"
    results = [
        {
            "rank": 1,
            "pmid": "123",
            "title": "Anti-TNF therapy in rheumatoid arthritis",
            "year": "2024",
            "journal": "NEJM",
            "similarity": 9.1,
        }
    ]
    provenance = build_provenance(
        disease_id=disease_id,
        module="semantic_search",
        sources=["pubmed"],
        query="anti-TNF therapy",
        cache_or_live="cache",
        run_id="ss-test-run",
    )

    report_path = generate_semantic_report(
        results,
        "anti-TNF therapy",
        indexed_count=42,
        disease_id=disease_id,
        provenance=provenance,
    )
    _assert_provenance_footer(_read_report(report_path), provenance, disease_id)


@pytest.mark.parametrize(
    ("command", "handler_name", "engine_fixture", "report_rel_path"),
    [
        (
            "synergy",
            "cmd_synergy",
            "synergy_pairs",
            "src/med_research/pipeline/drug_synergy/report.html",
        ),
        (
            "expression",
            "cmd_expression",
            "expression_results",
            "src/med_research/pipeline/gene_expression/report.html",
        ),
        (
            "cross-disease",
            "cmd_cross_disease",
            "cross_disease_analysis",
            "src/med_research/pipeline/cross_disease/report.html",
        ),
    ],
)
def test_cli_export_html_includes_provenance_footer(
    command,
    handler_name,
    engine_fixture,
    report_rel_path,
    monkeypatch,
    request,
):
    """CLI --export-html should produce reports with a provenance footer.

    Runs the real ``cmd_*`` handler in-process (arg parsing -> dispatch ->
    adapter -> report) against the shared session engine fixture, so each
    engine computes once per process instead of once per CLI subprocess.
    """
    from med_research.cli import cmd_cross_disease, cmd_expression, cmd_synergy
    from tests.cli_helpers import run_cli_handler

    handler = {
        "cmd_synergy": cmd_synergy,
        "cmd_expression": cmd_expression,
        "cmd_cross_disease": cmd_cross_disease,
    }[handler_name]

    patch_target = {
        "synergy": "med_research.pipeline.drug_synergy.engine.compute_synergy",
        "expression": "med_research.pipeline.gene_expression.correlator.compute_all_correlations",
        "cross-disease": "med_research.pipeline.cross_disease.analyzer.compute_cross_disease_analysis",
    }[command]
    engine_result = request.getfixturevalue(engine_fixture)
    monkeypatch.setattr(patch_target, lambda **kwargs: engine_result)

    report_path = PROJECT_ROOT / report_rel_path
    report_path.unlink(missing_ok=True)

    args = ["--export-html", "--top", "5", "--disease", "ra"]

    exit_code = run_cli_handler(handler, command, *args)
    assert exit_code == 0
    assert report_path.exists(), f"Expected report at {report_path}"

    html = _read_report(str(report_path))
    _assert_cli_provenance_footer(html)


def test_evidence_gatherer_report_provenance():
    from med_research.pipeline.evidence.gatherer_report import generate_html_report

    gathered = {
        "query": "rheumatoid arthritis treatment",
        "total_results": 1,
        "elapsed_seconds": 1.2,
        "results_by_source": {"pubmed": 1},
        "all_results": [
            {
                "source_type": "pubmed",
                "title": "Anti-TNF therapy in RA",
                "year": "2024",
                "snippet": "Clinical outcomes",
                "url": "https://example.com/1",
            }
        ],
        "crossref": {"pairs": []},
    }
    provenance = build_provenance(
        disease_id="ra",
        module="evidence_gather",
        sources=["pubmed"],
        query="rheumatoid arthritis treatment",
        cache_or_live="cache",
        run_id="eg-test-run",
    )

    report_path = generate_html_report(gathered, provenance=provenance)
    _assert_provenance_footer(_read_report(report_path), provenance, "ra")


def test_llm_extractor_report_provenance():
    from med_research.pipeline.evidence.extractor_report import generate_html_report

    results = {
        "query": "JAK inhibitor rheumatoid arthritis",
        "model": "gpt-4o-mini",
        "total_extracted": 1,
        "successful_extractions": 1,
        "elapsed_seconds": 2.5,
        "extractions": [
            {
                "title": "Tofacitinib in RA",
                "year": "2024",
                "source_type": "pubmed",
                "source": "PMID:123",
                "evidence_level": "rct",
                "model_system": "human",
                "key_findings": "Improved ACR response",
                "drugs_mentioned": ["tofacitinib"],
                "confidence": 85,
                "relevance_to_query": 90,
            }
        ],
        "stats": {
            "evidence_levels": {"rct": 1},
            "model_systems": {"human": 1},
            "study_designs": {"rct": 1},
            "unique_drugs_mentioned": ["tofacitinib"],
            "avg_confidence": 85.0,
            "n_unique_drugs": 1,
        },
    }
    provenance = build_provenance(
        disease_id="ra",
        module="llm_extractor",
        sources=["pubmed"],
        query="JAK inhibitor rheumatoid arthritis",
        cache_or_live="cache",
        model="gpt-4o-mini",
        run_id="le-test-run",
    )

    report_path = generate_html_report(results, provenance=provenance)
    _assert_provenance_footer(_read_report(report_path), provenance, "ra")


def test_evidence_monitor_report_provenance():
    from med_research.pipeline.evidence.monitor_report import generate_html_report

    prev_snapshot = {
        "snapshot_id": "20250101_120000",
        "queries": {"ra treatment": {"total": 1}},
        "drugs": {},
        "genes": {},
    }
    curr_snapshot = {
        "snapshot_id": "20250102_120000",
        "queries": {"ra treatment": {"total": 2}},
        "drugs": {},
        "genes": {},
    }
    diff = {
        "prev_snapshot": prev_snapshot["snapshot_id"],
        "curr_snapshot": curr_snapshot["snapshot_id"],
        "hours_elapsed": 24.0,
        "total_changes": 1,
        "alerts": [],
        "changes": {"changed_queries": ["ra treatment"], "changed_drugs": [], "changed_genes": []},
    }
    provenance = build_provenance(
        disease_id="ra",
        module="evidence_monitor",
        sources=["pubmed"],
        cache_or_live="cache",
        run_id="em-test-run",
    )

    report_path = generate_html_report(diff, prev_snapshot, curr_snapshot, provenance=provenance)
    _assert_provenance_footer(_read_report(report_path), provenance)
