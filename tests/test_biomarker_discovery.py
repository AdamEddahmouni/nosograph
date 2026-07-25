"""
Tests for the Biomarker Discovery module.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))  # noqa: I001

from med_research.pipeline.biomarker_discovery.discover import (
    analyze,
    compute_biomarker_matrix,
    map_gene_to_modules,
    score_biomarker,
)

# ── Unit: Gene Mapping ───────────────────────────────────────────────────


def test_map_gene_to_modules_returns_list():
    from med_research.pipeline.knowledge_graph.builder import build_graph
    G = build_graph()
    genes = {n: d for n, d in G.nodes(data=True) if d.get("type") == "gene"}
    matrix = map_gene_to_modules(genes, {})
    assert len(matrix) > 20
    for row in matrix:
        assert "gene_id" in row
        assert "gene_name" in row


def test_score_biomarker_range():
    row = {
        "gene_id": "TEST", "gene_name": "Test Gene",
        "consistency": 5.0, "expression_max": 5.0,
        "cart_score": 5.0, "repurpose_count": 2,
    }
    result = score_biomarker(row)
    assert 0.0 <= result["composite_score"] <= 10.0
    assert "tier" in result
    assert "best_modality" in result


def test_score_biomarker_all_fields():
    row = {
        "gene_id": "TEST", "gene_name": "Test",
        "consistency": 8.0, "expression_max": 9.0,
        "cart_score": 9.5, "repurpose_count": 4,
    }
    result = score_biomarker(row)
    for field in ["cross_module_consistency", "expression_predictiveness",
                   "cart_alignment", "druggability", "biomarker_novelty",
                   "best_modality"]:
        assert field in result


# ── Integration ──────────────────────────────────────────────────────────


def test_compute_biomarker_matrix():
    results = compute_biomarker_matrix()
    assert len(results) > 20
    assert results[0]["composite_score"] >= results[-1]["composite_score"]


def test_compute_biomarker_matrix_saves_json(tmp_path, monkeypatch):
    monkeypatch.setattr("med_research.pipeline.biomarker_discovery.discover.DATA_DIR", tmp_path)
    compute_biomarker_matrix()
    json_path = tmp_path / "biomarker_matrix.json"
    assert json_path.exists()
    data = json.loads(json_path.read_text())
    assert "biomarkers" in data


def test_analyze_prints(capsys):
    row = {
        "gene_id": "TEST", "gene_name": "Test Gene",
        "composite_score": 8.5, "cross_module_consistency": 8.0,
        "expression_predictiveness": 7.0, "cart_alignment": 9.0,
        "druggability": 8.0, "biomarker_novelty": 6.0,
        "best_modality": "CAR-T Therapy", "best_modality_score": 9.5,
        "tier": "Tier 1 — Strong Biomarker",
    }
    analyze([row])
    captured = capsys.readouterr()
    assert "1 genes analyzed" in captured.out


# ── Report ────────────────────────────────────────────────────────────────


def test_escape_html_biomarker():
    from med_research.pipeline.biomarker_discovery.report import escape_html
    assert escape_html("<script>") == "&lt;script&gt;"
    assert escape_html(None) == ""


@pytest.mark.slow
def test_generate_html_report():
    from med_research.pipeline.biomarker_discovery.report import generate_html_report

    results = compute_biomarker_matrix()
    path = generate_html_report(results)
    assert "report.html" in path
    assert Path(path).exists()
    Path(path).unlink(missing_ok=True)


# ── API Service ───────────────────────────────────────────────────────────


@pytest.mark.slow
def test_run_biomarker_analysis_service():
    from med_research.web.services.biomarker_service import run_biomarker_analysis

    result = run_biomarker_analysis(top_n=10)
    assert result["total_genes"] > 20
    assert len(result["biomarkers"]) == 10
    assert result["avg_score"] > 0


# ── CLI Integration ───────────────────────────────────────────────────────


@pytest.mark.slow
def test_biomarker_cli_help():
    import subprocess

    result = subprocess.run(
        [sys.executable, "main.py", "biomarker", "--help"],
        capture_output=True,
        text=True, encoding="utf-8", errors="replace",
        cwd=str(Path(__file__).parent.parent),
    )
    assert result.returncode == 0
    assert "biomarker" in result.stdout.lower()
