"""
Tests for the Gene Expression Correlation module.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from med_research.pipeline.gene_expression.correlator import (
    DRUG_CELL_TYPES,
    DRUG_PATHWAY_REVERSAL,
    DRUG_TARGET_GENES,
    SLE_DOWNREGULATED,
    SLE_UPREGULATED,
    analyze,
    compute_all_correlations,
    correlate_drug,
    load_drugs,
    score_cell_type_specificity,
    score_directionality,
    score_expression_evidence,
    score_signature_reversal,
    score_target_disease_overlap,
)
from med_research.pipeline.gene_expression.report import escape_html, generate_html_report

pytestmark = pytest.mark.unit


# ── Unit: Data Integrity ─────────────────────────────────────────────────


def test_sle_signature_not_empty():
    assert len(SLE_UPREGULATED) > 0
    assert len(SLE_DOWNREGULATED) > 0
    assert all(v >= 1.0 for v in SLE_UPREGULATED.values())
    assert all(v >= 1.0 for v in SLE_DOWNREGULATED.values())


def test_drug_target_mappings_not_empty():
    assert len(DRUG_TARGET_GENES) >= 15
    for _drug_id, targets in DRUG_TARGET_GENES.items():
        assert len(targets) > 0, f"{_drug_id} has no targets"


def test_drug_pathway_reversal_not_empty():
    assert len(DRUG_PATHWAY_REVERSAL) >= 5
    for _drug_id, data in DRUG_PATHWAY_REVERSAL.items():
        assert "downregulated_genes" in data or "upregulated_genes" in data
        assert "effect" in data


def test_cell_type_mappings():
    assert len(DRUG_CELL_TYPES) >= 10
    for _drug_id, cell_types in DRUG_CELL_TYPES.items():
        assert len(cell_types) > 0


# ── Unit: Scoring Functions ──────────────────────────────────────────────


def test_score_signature_reversal_range():
    drugs = load_drugs()
    for drug_id in drugs:
        score = score_signature_reversal(drug_id)
        assert 0.0 <= score <= 10.0


def test_score_signature_reversal_anifrolumab():
    score = score_signature_reversal("anifrolumab")
    assert score >= 7.0  # Strong IFN signature reversal


def test_score_target_disease_overlap_range():
    drugs = load_drugs()
    for drug_id in drugs:
        score = score_target_disease_overlap(drug_id)
        assert 0.0 <= score <= 10.0


def test_score_cell_type_specificity_range():
    drugs = load_drugs()
    for drug_id in drugs:
        score = score_cell_type_specificity(drug_id)
        assert 0.0 <= score <= 10.0


def test_score_expression_evidence_range():
    drugs = load_drugs()
    for drug_id in drugs:
        score = score_expression_evidence(drug_id)
        assert 0.0 <= score <= 10.0


def test_score_directionality_range():
    drugs = load_drugs()
    for drug_id in drugs:
        score = score_directionality(drug_id)
        assert 0.0 <= score <= 10.0


# ── Unit: Drug Correlation ────────────────────────────────────────────────


def test_correlate_drug_returns_all_fields():
    drugs = load_drugs()
    result = correlate_drug("anifrolumab", drugs["anifrolumab"])
    assert "drug_id" in result
    assert "drug_name" in result
    assert "signature_reversal" in result
    assert "target_disease_overlap" in result
    assert "cell_type_specificity" in result
    assert "expression_evidence" in result
    assert "directionality" in result
    assert "composite_score" in result
    assert "tier" in result


def test_correlate_drug_score_range():
    drugs = load_drugs()
    for drug_id in drugs:
        result = correlate_drug(drug_id, drugs[drug_id])
        assert 0.0 <= result["composite_score"] <= 10.0


# ── Integration: Full Analysis ───────────────────────────────────────────


def test_compute_all_correlations():
    results = compute_all_correlations()
    assert len(results) == 26
    scores = [r["composite_score"] for r in results]
    assert max(scores) > 6.0  # At least some drugs should score well
    assert results[0]["composite_score"] >= results[-1]["composite_score"]


def test_compute_all_correlations_saves_json(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "med_research.pipeline.gene_expression.correlator.DATA_DIR",
        tmp_path,
    )
    compute_all_correlations()
    json_path = tmp_path / "expression_correlations_sle.json"
    assert json_path.exists()
    data = json.loads(json_path.read_text())
    assert "drugs" in data
    assert data["total_drugs"] == 26


def test_compute_all_correlations_save_false_skips_write(tmp_path, monkeypatch):
    """save=False must not write the per-disease expression correlations file."""
    monkeypatch.setattr(
        "med_research.pipeline.gene_expression.correlator.DATA_DIR",
        tmp_path,
    )
    compute_all_correlations(save=False)
    assert not (tmp_path / "expression_correlations_sle.json").exists()
    # And save=True still writes
    compute_all_correlations(save=True)
    assert (tmp_path / "expression_correlations_sle.json").exists()


def test_analyze_prints(caplog):
    drug = {
        "drug_id": "test",
        "drug_name": "Test Drug",
        "composite_score": 8.5,
        "signature_reversal": 9.0,
        "target_disease_overlap": 8.0,
        "cell_type_specificity": 7.0,
        "expression_evidence": 6.0,
        "directionality": 10.0,
        "tier": "🔴 Tier 1 — Strong Expression Reversal",
    }
    analyze([drug])
    assert "1 drugs scored" in caplog.text


# ── Report ────────────────────────────────────────────────────────────────


def test_escape_html_expression():
    assert escape_html("<script>") == "&lt;script&gt;"
    assert escape_html(None) == ""
    assert escape_html("safe") == "safe"


def test_generate_html_report():
    results = compute_all_correlations()
    path = generate_html_report(results)
    assert "report.html" in path
    assert Path(path).exists()
    Path(path).unlink(missing_ok=True)


# ── API Service ───────────────────────────────────────────────────────────


def test_run_correlation_analysis_service():
    from med_research.web.services.expression_service import run_correlation_analysis

    result = run_correlation_analysis(top_n=10)
    assert result["total_drugs"] == 26
    assert len(result["drugs"]) == 10
    assert result["avg_score"] > 0
    assert "tier1_count" in result


# ── CLI Integration ───────────────────────────────────────────────────────


def test_expression_cli_help():
    from tests.cli_helpers import cli_help_output

    help_text = cli_help_output("expression", "--help")
    assert "expression" in help_text.lower()


# ── GEO Multi-Omics Integration ───────────────────────────────────────────


MOCK_GEO_SEARCH_RESPONSE = {
    "esearchresult": {
        "count": "3",
        "retmax": "3",
        "idlist": ["200000001", "200000002", "200000003"],
    }
}

MOCK_GEO_SUMMARY_RESPONSE = {
    "result": {
        "uids": ["200000001", "200000002", "200000003"],
        "200000001": {
            "accession": "GSE100001",
            "gse": "GSE100001",
            "title": "PBMC expression profiling in SLE patients",
            "summary": "Transcriptomic analysis of PBMCs from SLE patients vs controls",
            "taxon": "Homo sapiens",
            "gdsType": "Expression profiling by array",
            "samples": "87",
            "pubmedIds": ["30123456"],
            "PTechType": "GPL570",
        },
        "200000002": {
            "accession": "GSE100002",
            "gse": "GSE100002",
            "title": "Whole blood transcriptome of SLE patients",
            "summary": "RNA-seq of whole blood from active SLE patients",
            "taxon": "Homo sapiens",
            "gdsType": "Expression profiling by high throughput sequencing",
            "samples": "120",
            "pubmedIds": ["31234567"],
            "PTechType": "Illumina HiSeq",
        },
        "200000003": {
            "accession": "GSE100003",
            "gse": "GSE100003",
            "title": "Kidney biopsy expression in lupus nephritis",
            "summary": "Microarray analysis of kidney biopsies from LN patients",
            "taxon": "Homo sapiens",
            "gdsType": "Expression profiling by array",
            "samples": "45",
            "pubmedIds": ["32345678"],
            "PTechType": "GPL96",
        },
    }
}


def _mock_requests_get(url, params, timeout=15):
    class MockResponse:
        def __init__(self, data, status=200):
            self._data = data
            self.status_code = status

        def json(self):
            return self._data

        def raise_for_status(self):
            if self.status_code >= 400:
                raise Exception("HTTP error")

    if "esearch" in url:
        return MockResponse(MOCK_GEO_SEARCH_RESPONSE)
    elif "esummary" in url:
        return MockResponse(MOCK_GEO_SUMMARY_RESPONSE)
    return MockResponse({}, status=404)


def test_geo_search_broad(monkeypatch):
    monkeypatch.setattr(
        "med_research.pipeline.gene_expression.geo.requests.get", _mock_requests_get
    )
    from med_research.pipeline.gene_expression.geo import search_geo_datasets

    studies = search_geo_datasets(disease="sle", category="broad", no_cache=True)
    assert len(studies) >= 2
    assert all("accession" in s for s in studies)
    assert any(s["accession"] == "GSE100001" for s in studies)


def test_geo_search_ra_uses_disease_specific_terms(monkeypatch):
    """RA GEO search must not reuse SLE query terms."""
    captured_terms: list[str] = []

    def capture_term(url, params, timeout=15):
        if "esearch" in url:
            captured_terms.append(params.get("term", ""))
        return _mock_requests_get(url, params, timeout)

    monkeypatch.setattr(
        "med_research.pipeline.gene_expression.geo.requests.get",
        capture_term,
    )
    from med_research.pipeline.gene_expression.geo import search_geo_datasets

    search_geo_datasets(disease="ra", category="broad", no_cache=True)
    assert captured_terms
    ra_term = captured_terms[0]
    assert "rheumatoid arthritis" in ra_term.lower()
    assert "lupus" not in ra_term.lower()
    assert "systemic lupus" not in ra_term.lower()


def test_geo_search_ibd_differs_from_sle(monkeypatch):
    """IBD and SLE broad searches must issue different Entrez term strings."""
    captured: dict[str, str] = {}

    def capture_term(url, params, timeout=15):
        if "esearch" in url:
            captured[params.get("db", "gds")] = params.get("term", "")
        return _mock_requests_get(url, params, timeout)

    monkeypatch.setattr(
        "med_research.pipeline.gene_expression.geo.requests.get",
        capture_term,
    )
    from med_research.pipeline.gene_expression.geo import search_geo_datasets

    search_geo_datasets(disease="sle", category="broad", no_cache=True)
    sle_term = captured.get("gds", "")
    captured.clear()

    search_geo_datasets(disease="ibd", category="broad", no_cache=True)
    ibd_term = captured.get("gds", "")

    assert sle_term
    assert ibd_term
    assert sle_term != ibd_term
    assert "inflammatory bowel disease" in ibd_term.lower() or "crohn" in ibd_term.lower()
    assert "lupus" not in ibd_term.lower()


def test_geo_search_cache(monkeypatch, tmp_path):
    from med_research.cache import CacheManager
    from med_research.pipeline.gene_expression import geo

    cache_root = tmp_path / "central_cache"
    geo_cache_root = tmp_path / "geo_cache"
    geo_cache_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(geo, "CACHE_DIR", geo_cache_root)
    monkeypatch.setattr(
        "med_research.cache.get_cache_manager",
        lambda: CacheManager(cache_dir=cache_root),
    )
    monkeypatch.setattr(
        "med_research.pipeline.gene_expression.geo.requests.get",
        _mock_requests_get,
    )

    studies1 = geo.search_geo_datasets(disease="sle", category="broad", no_cache=False)
    assert len(studies1) >= 2

    hit_count = 0

    def counting_mock(url, params, timeout=15):
        nonlocal hit_count
        hit_count += 1
        return _mock_requests_get(url, params, timeout)

    monkeypatch.setattr(
        "med_research.pipeline.gene_expression.geo.requests.get",
        counting_mock,
    )

    studies2 = geo.search_geo_datasets(disease="sle", category="broad", no_cache=False)
    assert hit_count == 0
    assert studies1 == studies2


def _quota_error_response():
    class _Response:
        status_code = 429
        headers = {"Retry-After": "5"}

    return _Response()


def test_geo_search_retries_quota_with_retry_after(monkeypatch):
    """A 429 with Retry-After is retried via backoff_sleep, then succeeds."""
    import requests

    from med_research.pipeline.gene_expression import geo

    esearch_calls = {"count": 0}

    def quota_then_success(url, params=None, timeout=15):
        if "esearch" in url:
            esearch_calls["count"] += 1
            if esearch_calls["count"] == 1:
                raise requests.exceptions.HTTPError(response=_quota_error_response())
        return _mock_requests_get(url, params, timeout)

    slept: list[dict] = []
    monkeypatch.setattr(
        "med_research.exceptions.backoff_sleep",
        lambda attempt, **kwargs: slept.append({"attempt": attempt, **kwargs}),
    )
    monkeypatch.setattr(
        "med_research.pipeline.gene_expression.geo.requests.get",
        quota_then_success,
    )

    studies = geo.search_geo_datasets(disease="sle", category="broad", no_cache=True)

    assert len(studies) >= 2
    # First esearch attempt hit the quota; the retry succeeded.
    assert esearch_calls["count"] == 2
    assert slept == [{"attempt": 0, "retry_after": 5.0}]


def test_geo_search_degrades_after_persistent_timeout(monkeypatch):
    """A persistent timeout is retried with backoff, then degrades to []"""
    import requests

    from med_research.pipeline.gene_expression import geo

    def always_timeout(url, params=None, timeout=15):
        raise requests.exceptions.Timeout("timed out")

    monkeypatch.setattr(
        "med_research.exceptions.backoff_sleep",
        lambda attempt, **kwargs: None,
    )
    monkeypatch.setattr(
        "med_research.pipeline.gene_expression.geo.requests.get",
        always_timeout,
    )

    studies = geo.search_geo_datasets(disease="sle", category="broad", no_cache=True)
    assert studies == []


def test_build_consensus_signature():
    from med_research.pipeline.gene_expression.geo import build_consensus_signature

    studies = [{"accession": "GSE100001"}, {"accession": "GSE100002"}]
    sig = build_consensus_signature(studies, disease="sle", min_occurrence=2)

    assert sig["source"] == "geo_consensus"
    assert sig["coverage"] == "curated"
    assert sig["num_studies_used"] == 2
    assert len(sig["upregulated"]) > 0
    assert len(sig["downregulated"]) > 0
    assert all("fold_change" in v for v in sig["upregulated"].values())
    assert all("confidence" in v for v in sig["upregulated"].values())
    assert sig["study_ids"] == ["GSE100001", "GSE100002"]


def test_build_consensus_signature_ra():
    from med_research.pipeline.gene_expression.geo import build_consensus_signature

    studies = [{"accession": "GSE200001"}, {"accession": "GSE200002"}]
    sig = build_consensus_signature(studies, disease="ra", min_occurrence=2)

    assert sig["coverage"] == "curated"
    assert sig["disease"] == "ra"
    assert "TNF" in sig["upregulated"]
    assert "IRF5" not in sig["upregulated"]


def test_build_consensus_signature_ibd():
    from med_research.pipeline.gene_expression.geo import build_consensus_signature

    studies = [{"accession": "GSE300001"}]
    sig = build_consensus_signature(studies, disease="ibd", min_occurrence=1)

    assert sig["coverage"] == "curated"
    assert sig["disease"] == "ibd"
    assert "TNF" in sig["upregulated"]
    assert "MUC2" in sig["downregulated"]


def test_build_consensus_signature_ms():
    from med_research.pipeline.gene_expression.geo import build_consensus_signature

    studies = [{"accession": "GSE400001"}]
    sig = build_consensus_signature(studies, disease="ms", min_occurrence=1)

    assert sig["coverage"] == "curated"
    assert sig["disease"] == "ms"
    assert "IL7R" in sig["upregulated"]
    assert "MBP" in sig["downregulated"]
    assert "IRF5" not in sig["upregulated"]


@pytest.mark.parametrize(
    "disease_id,up_gene,down_gene",
    [
        ("ms", "IL7R", "MBP"),
        ("ss", "TNFSF13B", "AQP5"),
        ("ssc", "COL1A1", "PPARG"),
        ("t1d", "PTPN22", "PDX1"),
        ("nsclc", "EGFR", "CDKN2A"),
        ("pancreatic_ductal_adenocarcinoma", "KRAS", "SMAD4"),
        ("glioblastoma", "EGFR", "PTEN"),
        ("cystic_fibrosis", "TGFB1", "CFTR"),
        ("sickle_cell_anemia", "SELP", "NOS3"),
        ("heart_failure", "MYH7", "ADRB1"),
        ("non_alcoholic_fatty_liver_disease", "PNPLA3", "ATG7"),
    ],
)
def test_build_consensus_signature_new_diseases(disease_id, up_gene, down_gene):
    from med_research.pipeline.gene_expression.geo import build_consensus_signature

    studies = [{"accession": f"GSE_{disease_id}"}]
    sig = build_consensus_signature(studies, disease=disease_id, min_occurrence=1)

    assert sig["coverage"] == "curated"
    assert sig["disease"] == disease_id
    assert up_gene in sig["upregulated"]
    assert down_gene in sig["downregulated"]
    assert "IRF5" not in sig["upregulated"]
    assert "IFI44L" not in sig["upregulated"]


def test_build_consensus_signature_unsupported_disease():
    from med_research.pipeline.gene_expression.geo import build_consensus_signature

    studies = [{"accession": "GSE400001"}]
    sig = build_consensus_signature(studies, disease="unknown_disease", min_occurrence=1)

    assert sig["coverage"] == "not_curated"
    assert sig["upregulated"] == {}
    assert sig["downregulated"] == {}
    assert "note" in sig


def test_fetch_expression_data_reports_status():
    from med_research.pipeline.gene_expression.geo import fetch_expression_data

    result = fetch_expression_data("GSE999999")
    assert result["status"] == "not_implemented"
    assert result["coverage"] == "download_not_implemented"
    assert result["path"] is None
    assert "message" in result


def test_build_consensus_with_tissue():
    from med_research.pipeline.gene_expression.geo import build_consensus_signature

    studies = [{"accession": "GSE100003"}]
    sig = build_consensus_signature(studies, disease="sle", min_occurrence=2, tissue="kidney")
    assert sig["tissue_category"] == "kidney"
    kidney_genes = {"CCL2", "CCL5", "TNF", "IL6", "STAT1", "IKZF1", "PRDM1"}
    for gene in sig["upregulated"]:
        assert gene in kidney_genes


def test_build_consensus_empty_studies():
    from med_research.pipeline.gene_expression.geo import build_consensus_signature

    sig = build_consensus_signature([], disease="sle", min_occurrence=2)
    assert sig["num_studies_used"] == 0
    assert sig["upregulated"] == {}
    assert sig["downregulated"] == {}


def test_signature_manager_curated():
    from med_research.pipeline.gene_expression.signature import get_signature

    sig = get_signature(disease="sle", source="curated")
    assert sig["source"] == "curated_consensus"
    assert sig["coverage"] == "curated"
    assert len(sig["upregulated"]) > 0
    assert len(sig["downregulated"]) > 0
    assert "IRF5" in sig["upregulated"]
    assert "C1QA" in sig["downregulated"]


def test_get_signature_fallback(monkeypatch):
    def mock_get_expression_sig(disease=None, tissue=None, min_studies=2):
        return {"num_studies_used": 0, "upregulated": {}, "downregulated": {}}

    monkeypatch.setattr(
        "med_research.pipeline.gene_expression.geo.get_expression_signature",
        mock_get_expression_sig,
    )
    from med_research.pipeline.gene_expression.signature import get_signature

    sig = get_signature(disease="sle", source="auto")
    assert sig["source"] == "curated_consensus"
    assert len(sig["upregulated"]) > 0


def test_correlate_with_geo_signature():
    from med_research.pipeline.gene_expression.correlator import correlate_drug, load_drugs
    from med_research.pipeline.gene_expression.signature import get_signature

    sig = get_signature(disease="sle", source="curated")
    drugs = load_drugs()
    result = correlate_drug("anifrolumab", drugs["anifrolumab"], signature=sig)
    assert result["composite_score"] >= 6.0
    assert result["signature_reversal"] >= 7.0


# ── Disease threading ───────────────────────────────────────────────────


def test_load_drugs_threads_disease(monkeypatch):
    import med_research.pipeline.gene_expression.correlator as correlator

    captured = {}

    def fake_config_load_drugs(disease_id="sle"):
        captured["disease_id"] = disease_id
        return {"drugs": [{"id": "baricitinib", "name": "Baricitinib"}]}

    monkeypatch.setattr(correlator, "config_load_drugs", fake_config_load_drugs)
    drugs = correlator.load_drugs("ms")
    assert captured["disease_id"] == "ms"
    assert "baricitinib" in drugs


def test_get_default_signature_is_per_disease():
    import med_research.pipeline.gene_expression.correlator as correlator

    correlator._DEFAULT_SIGNATURES.clear()
    sig_sle = correlator._get_default_signature("sle")
    sig_ra = correlator._get_default_signature("ra")
    sig_ms = correlator._get_default_signature("ms")
    assert sig_sle["disease"] == "sle"
    assert sig_ra["disease"] == "ra"
    assert sig_ms["disease"] == "ms"
    assert "IRF5" in sig_sle["upregulated"]
    assert "TNF" in sig_ra["upregulated"]
    assert "IL7R" in sig_ms["upregulated"]
    assert "IRF5" not in sig_ms["upregulated"]
    assert sig_ra["upregulated"].keys() != sig_sle["upregulated"].keys()


def test_compute_all_correlations_threads_disease(monkeypatch):
    import med_research.pipeline.gene_expression.correlator as correlator

    captured = {}

    def fake_load_drugs(disease_id="sle"):
        captured["disease_id"] = disease_id
        return {"baricitinib": {"id": "baricitinib", "name": "Baricitinib"}}

    monkeypatch.setattr(correlator, "load_drugs", fake_load_drugs)
    # Avoid GEO/curated signature machinery; pass a tiny explicit signature
    results = correlator.compute_all_correlations(
        disease_id="ra",
        signature={"upregulated": {}, "downregulated": {}, "source": "test", "num_studies_used": 0},
        signature_source="curated",
    )
    assert captured["disease_id"] == "ra"
    assert len(results) == 1
    assert results[0]["drug_id"] == "baricitinib"


def test_cli_geo_flag(monkeypatch):
    from med_research.pipeline.gene_expression.signature import get_signature

    sig = get_signature(disease="sle", source="curated")
    from med_research.pipeline.gene_expression.correlator import _normalize_signature

    up_genes, down_genes, sig_source, num_studies = _normalize_signature(sig)
    assert sig_source in ("curated_consensus", "geo_consensus", "geo_fallback")
    assert len(up_genes) > 0
    assert len(down_genes) > 0


def test_expression_report_with_signature_source():
    from med_research.pipeline.gene_expression.correlator import compute_all_correlations
    from med_research.pipeline.gene_expression.report import generate_html_report

    results = compute_all_correlations()
    path = generate_html_report(
        results[:5], signature_source="curated_consensus", num_studies=0, tissue="broad"
    )
    content = Path(path).read_text(encoding="utf-8")
    assert "Expression Signature Source" in content
    assert "curated_consensus" in content
    Path(path).unlink(missing_ok=True)


L3_WAVE_DISEASES = (
    "nsclc",
    "pancreatic_ductal_adenocarcinoma",
    "glioblastoma",
    "cystic_fibrosis",
    "sickle_cell_anemia",
    "heart_failure",
    "non_alcoholic_fatty_liver_disease",
)

L3_TISSUE_CASES = (
    ("nsclc", "lung", "EGFR", "CDKN2A"),
    ("pancreatic_ductal_adenocarcinoma", "pancreas", "KRAS", "SMAD4"),
    ("glioblastoma", "tumor", "EGFR", "PTEN"),
    ("cystic_fibrosis", "airway", "TGFB1", "CFTR"),
    ("sickle_cell_anemia", "pbmc_blood", "SELP", "NOS3"),
    ("heart_failure", "myocardium", "MYH7", "ADRB1"),
    ("non_alcoholic_fatty_liver_disease", "liver", "PNPLA3", "ATG7"),
)


@pytest.mark.parametrize("disease_id", L3_WAVE_DISEASES)
def test_wave_l3_curated_signature_manager(disease_id):
    from med_research.pipeline.gene_expression.signature import get_signature

    sig = get_signature(disease=disease_id, source="curated")
    assert sig["coverage"] == "curated"
    assert sig["source"] == "curated_consensus"
    assert sig["upregulated"]
    assert sig["downregulated"]
    assert "IRF5" not in sig["upregulated"]


@pytest.mark.parametrize("disease_id", L3_WAVE_DISEASES)
def test_wave_l3_consensus_symbols_exist_in_kg(disease_id):
    from med_research.diseases.base import Disease
    from med_research.pipeline.gene_expression.geo import DISEASE_CONSENSUS_GENES

    kg_ids = {g["id"] for g in Disease(disease_id).load_genes().get("genes", [])}
    consensus = DISEASE_CONSENSUS_GENES[disease_id]
    missing = (set(consensus["upregulated"]) | set(consensus["downregulated"])) - kg_ids
    assert not missing, f"{disease_id} consensus symbols missing from genes.json: {sorted(missing)}"


@pytest.mark.parametrize("disease_id,tissue,up_gene,down_gene", L3_TISSUE_CASES)
def test_wave_l3_tissue_filters(disease_id, tissue, up_gene, down_gene):
    from med_research.pipeline.gene_expression.geo import build_consensus_signature

    sig = build_consensus_signature(
        [{"accession": "TEST"}],
        disease=disease_id,
        min_occurrence=1,
        tissue=tissue,
    )
    assert sig["coverage"] == "curated"
    assert sig["tissue_category"] == tissue
    assert up_gene in sig["upregulated"]
    assert down_gene in sig["downregulated"]
    assert "IRF5" not in sig["upregulated"]
