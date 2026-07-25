"""
Tests for the CAR-T Response Predictor module.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from med_research.pipeline.car_t_predictor.predictor import (
    B_CELL_DEPENDENCY,
    CAR_T_EVIDENCE,
    CD19_TARGETING,
    analyze,
    compute_all_scores,
    load_genes,
    score_gene,
)

# ── Unit: Data Integrity ─────────────────────────────────────────────────


def test_gene_database_loads():
    genes = load_genes()
    assert len(genes) >= 35
    assert "CD19" in genes or "CD20" in genes


def test_scoring_dictionaries_not_empty():
    assert len(B_CELL_DEPENDENCY) >= 30
    assert len(CAR_T_EVIDENCE) >= 30
    assert len(CD19_TARGETING) >= 30


def test_scoring_values_in_range():
    for score in B_CELL_DEPENDENCY.values():
        assert 0.0 <= score <= 10.0
    for score in CAR_T_EVIDENCE.values():
        assert 0.0 <= score <= 10.0
    for score in CD19_TARGETING.values():
        assert 0.0 <= score <= 10.0


# ── Unit: Gene Scoring ───────────────────────────────────────────────────


def test_score_gene_returns_all_fields():
    genes = load_genes()
    result = score_gene("PRDM1", genes["PRDM1"])
    assert "gene_id" in result
    assert "b_cell_dependency" in result
    assert "autoantibody_association" in result
    assert "plasma_cell_relevance" in result
    assert "cd19_targeting" in result
    assert "clinical_evidence" in result
    assert "composite_score" in result
    assert "tier" in result
    assert "recommendation" in result


def test_score_gene_prdm1_top():
    """PRDM1 (BLIMP-1) should score very high — plasma cell master regulator."""
    genes = load_genes()
    result = score_gene("PRDM1", genes["PRDM1"])
    assert result["composite_score"] >= 9.0


def test_score_gene_c1qa_low():
    """C1QA (complement) should score low — not B cell driven."""
    genes = load_genes()
    result = score_gene("C1QA", genes["C1QA"])
    assert result["composite_score"] < 5.0


def test_score_gene_range():
    genes = load_genes()
    for gene_id in genes:
        result = score_gene(gene_id, genes[gene_id])
        assert 0.0 <= result["composite_score"] <= 10.0


# ── Integration: Full Analysis ───────────────────────────────────────────


def test_compute_all_scores():
    results = compute_all_scores()
    assert len(results) >= 35
    assert results[0]["composite_score"] >= 9.0
    assert results[-1]["composite_score"] <= results[0]["composite_score"]


def test_compute_all_scores_saves_json(tmp_path, monkeypatch):
    monkeypatch.setattr("med_research.pipeline.car_t_predictor.predictor.DATA_DIR", tmp_path)
    compute_all_scores()
    json_path = tmp_path / "car_t_scores.json"
    assert json_path.exists()
    data = json.loads(json_path.read_text())
    assert "genes" in data
    assert data["total_genes"] >= 35


def test_analyze_prints(capsys):
    genes = load_genes()
    gene = score_gene("PRDM1", genes["PRDM1"])
    analyze([gene])
    captured = capsys.readouterr()
    assert "1 genes scored" in captured.out


# ── Report ────────────────────────────────────────────────────────────────


def test_escape_html_cart():
    from med_research.pipeline.car_t_predictor.report import escape_html
    assert escape_html("<script>") == "&lt;script&gt;"
    assert escape_html(None) == ""


@pytest.mark.slow
def test_generate_html_report():
    from med_research.pipeline.car_t_predictor.report import generate_html_report

    results = compute_all_scores()
    path = generate_html_report(results)
    assert "report.html" in path
    assert Path(path).exists()
    Path(path).unlink(missing_ok=True)


# ── API Service ───────────────────────────────────────────────────────────


@pytest.mark.slow
def test_run_cart_analysis_service():
    from med_research.web.services.car_t_service import run_cart_analysis

    result = run_cart_analysis(top_n=10)
    assert result["total_genes"] >= 35
    assert len(result["genes"]) == 10
    assert result["avg_score"] > 0
    assert "tier1_count" in result


# ── CLI Integration ───────────────────────────────────────────────────────


@pytest.mark.slow
def test_cart_cli_help():
    import subprocess

    result = subprocess.run(
        [sys.executable, "main.py", "cart", "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(Path(__file__).parent.parent),
    )
    assert result.returncode == 0
    assert "cart" in result.stdout.lower()
