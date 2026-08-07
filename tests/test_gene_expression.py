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
    json_path = tmp_path / "expression_correlations.json"
    assert json_path.exists()
    data = json.loads(json_path.read_text())
    assert "drugs" in data
    assert data["total_drugs"] == 26


def test_compute_all_correlations_save_false_skips_write(tmp_path, monkeypatch):
    """save=False must not write the shared expression_correlations.json."""
    monkeypatch.setattr(
        "med_research.pipeline.gene_expression.correlator.DATA_DIR",
        tmp_path,
    )
    compute_all_correlations(save=False)
    assert not (tmp_path / "expression_correlations.json").exists()
    # And save=True still writes
    compute_all_correlations(save=True)
    assert (tmp_path / "expression_correlations.json").exists()


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


@pytest.mark.slow
def test_generate_html_report():
    results = compute_all_correlations()
    path = generate_html_report(results)
    assert "report.html" in path
    assert Path(path).exists()
    Path(path).unlink(missing_ok=True)


# ── API Service ───────────────────────────────────────────────────────────


@pytest.mark.slow
def test_run_correlation_analysis_service():
    from med_research.web.services.expression_service import run_correlation_analysis

    result = run_correlation_analysis(top_n=10)
    assert result["total_drugs"] == 26
    assert len(result["drugs"]) == 10
    assert result["avg_score"] > 0
    assert "tier1_count" in result


# ── CLI Integration ───────────────────────────────────────────────────────


@pytest.mark.slow
def test_expression_cli_help():
    import subprocess

    result = subprocess.run(
        [sys.executable, "main.py", "expression", "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(Path(__file__).parent.parent),
    )
    assert result.returncode == 0
    assert "expression" in result.stdout.lower()


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
    monkeypatch.setattr("med_research.pipeline.gene_expression.geo.requests.get", _mock_requests_get)
    from med_research.pipeline.gene_expression.geo import search_geo_datasets

    studies = search_geo_datasets(disease="sle", category="broad", no_cache=True)
    assert len(studies) >= 2
    assert all("accession" in s for s in studies)
    assert any(s["accession"] == "GSE100001" for s in studies)


def test_geo_search_cache(monkeypatch, tmp_path):
    from med_research.pipeline.gene_expression import geo
    monkeypatch.setattr(geo, "CACHE_DIR", tmp_path)
    monkeypatch.setattr("med_research.pipeline.gene_expression.geo.requests.get", _mock_requests_get)

    studies1 = geo.search_geo_datasets(disease="sle", category="broad", no_cache=True)
    assert len(studies1) >= 2

    hit_count = 0
    def counting_mock(url, params, timeout=15):
        nonlocal hit_count
        hit_count += 1
        return _mock_requests_get(url, params, timeout)
    monkeypatch.setattr("med_research.pipeline.gene_expression.geo.requests.get", counting_mock)

    studies2 = geo.search_geo_datasets(disease="sle", category="broad", no_cache=False)
    assert hit_count == 0
    assert studies1 == studies2


def test_build_consensus_signature():
    from med_research.pipeline.gene_expression.geo import build_consensus_signature

    studies = [{"accession": "GSE100001"}, {"accession": "GSE100002"}]
    sig = build_consensus_signature(studies, disease="sle", min_occurrence=2)

    assert sig["source"] == "geo_consensus"
    assert sig["num_studies_used"] == 2
    assert len(sig["upregulated"]) > 0
    assert len(sig["downregulated"]) > 0
    assert all("fold_change" in v for v in sig["upregulated"].values())
    assert all("confidence" in v for v in sig["upregulated"].values())
    assert sig["study_ids"] == ["GSE100001", "GSE100002"]


def test_build_consensus_with_tissue():
    from med_research.pipeline.gene_expression.geo import build_consensus_signature

    studies = [{"accession": "GSE100003"}]
    sig = build_consensus_signature(studies, disease="sle",
                                    min_occurrence=2, tissue="kidney")
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
    assert sig["source"] == "curated_literature"
    assert len(sig["upregulated"]) > 0
    assert len(sig["downregulated"]) > 0
    assert "IRF5" in sig["upregulated"]
    assert "C1QA" in sig["downregulated"]


def test_get_signature_fallback(monkeypatch):
    def mock_get_expression_sig(disease=None, tissue=None, min_studies=2):
        return {"num_studies_used": 0, "upregulated": {}, "downregulated": {}}

    monkeypatch.setattr("med_research.pipeline.gene_expression.geo.get_expression_signature",
                        mock_get_expression_sig)
    from med_research.pipeline.gene_expression.signature import get_signature

    sig = get_signature(disease="sle", source="auto")
    assert sig["source"] == "curated_literature"
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

    sig_sle = correlator._get_default_signature("sle")
    sig_ra = correlator._get_default_signature("ra")
    assert sig_sle["disease"] == "sle"
    assert sig_ra["disease"] == "ra"
    # Both fall back to the curated SLE gene set (documented stand-in)
    assert sig_ra["upregulated"]
    assert sig_sle["upregulated"].keys() == sig_ra["upregulated"].keys()


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
        signature={"upregulated": {}, "downregulated": {},
                   "source": "test", "num_studies_used": 0},
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
    assert sig_source in ("curated_literature", "geo_consensus", "geo_fallback")
    assert len(up_genes) > 0
    assert len(down_genes) > 0


def test_expression_report_with_signature_source():
    from med_research.pipeline.gene_expression.correlator import compute_all_correlations
    from med_research.pipeline.gene_expression.report import generate_html_report

    results = compute_all_correlations()
    path = generate_html_report(results, signature_source="curated_literature",
                                num_studies=0, tissue="broad")
    content = Path(path).read_text(encoding="utf-8")
    assert "Expression Signature Source" in content
    assert "curated_literature" in content
    Path(path).unlink(missing_ok=True)
