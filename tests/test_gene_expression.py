"""
Tests for the Gene Expression Correlation module.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from gene_expression.correlator import (
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
from gene_expression.report import escape_html, generate_html_report

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
        "gene_expression.correlator.DATA_DIR",
        tmp_path,
    )
    compute_all_correlations()
    json_path = tmp_path / "expression_correlations.json"
    assert json_path.exists()
    data = json.loads(json_path.read_text())
    assert "drugs" in data
    assert data["total_drugs"] == 26


def test_analyze_prints(capsys):
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
    captured = capsys.readouterr()
    assert "1 drugs scored" in captured.out


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
    from web_api.services.expression_service import run_correlation_analysis

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
