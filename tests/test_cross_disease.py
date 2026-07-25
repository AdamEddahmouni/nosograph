"""
Tests for the Cross-Disease Drug Repurposing module (Phase 22).
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from cross_disease.analyzer import (
    _assign_tier,
    _jaccard,
    _normalize_drug_id,
    _normalize_gene_id,
    analyze,
    compute_cross_disease_analysis,
    compute_cross_disease_repurposing,
    compute_disease_similarity,
    compute_shared_drugs,
    compute_shared_genes,
    compute_shared_pathways,
    load_all_disease_data,
    print_repurposing,
    print_top_drugs,
    score_multi_disease_drugs,
)

# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def all_data():
    return load_all_disease_data()


@pytest.fixture(scope="module")
def analysis_results():
    return compute_cross_disease_analysis()


# ── Unit: Data Loading ─────────────────────────────────────────────────────


def test_load_all_disease_data_returns_7():
    data = load_all_disease_data()
    assert len(data) == 7, f"Expected 7 diseases, got {len(data)}"
    for did in ["sle", "ra", "ms", "ss", "ssc", "t1d", "ibd"]:
        assert did in data


def test_load_all_disease_data_has_all_keys(all_data):
    for did, d_data in all_data.items():
        for key in ["profile", "name", "genes", "drugs", "pathways", "relationships"]:
            assert key in d_data, f"{did} missing key '{key}'"


def test_sle_has_most_genes(all_data):
    sle_genes = len(all_data["sle"]["genes"].get("genes", []))
    for did in ["ra", "ms", "ibd"]:
        other_genes = len(all_data[did]["genes"].get("genes", []))
        assert sle_genes >= other_genes


# ── Unit: Normalization ────────────────────────────────────────────────────


def test_normalize_gene_id():
    assert _normalize_gene_id("btk") == "BTK"
    assert _normalize_gene_id("  Hla-drb1 ") == "HLA-DRB1"
    assert _normalize_gene_id("STAT4") == "STAT4"


def test_normalize_drug_id():
    assert _normalize_drug_id("Rituximab") == "rituximab"
    assert _normalize_drug_id("  Prednisone ") == "prednisone"
    assert _normalize_drug_id("Methotrexate") == "methotrexate"


# ── Unit: Jaccard ──────────────────────────────────────────────────────────


def test_jaccard_identical():
    assert _jaccard({"a", "b"}, {"a", "b"}) == 1.0


def test_jaccard_disjoint():
    assert _jaccard({"a", "b"}, {"c", "d"}) == 0.0


def test_jaccard_partial():
    assert _jaccard({"a", "b", "c"}, {"b", "c", "d"}) == 0.5


def test_jaccard_empty():
    assert _jaccard(set(), {"a"}) == 0.0


# ── Unit: Shared Genes ─────────────────────────────────────────────────────


def test_compute_shared_genes_returns_dict(all_data):
    result = compute_shared_genes(all_data)
    assert "shared_genes" in result
    assert "gene_disease_count" in result


def test_compute_shared_genes_finds_ptpn22(all_data):
    result = compute_shared_genes(all_data)
    shared = {g["gene_id"]: g for g in result["shared_genes"]}
    assert "PTPN22" in shared
    assert shared["PTPN22"]["disease_count"] >= 4


def test_compute_shared_genes_sorted_by_count(all_data):
    result = compute_shared_genes(all_data)
    shared = result["shared_genes"]
    for i in range(len(shared) - 1):
        assert shared[i]["disease_count"] >= shared[i + 1]["disease_count"]


# ── Unit: Shared Drugs ─────────────────────────────────────────────────────


def test_compute_shared_drugs_returns_dict(all_data):
    result = compute_shared_drugs(all_data)
    assert "shared_drugs" in result
    assert "drug_disease_count" in result


def test_compute_shared_drugs_finds_rituximab(all_data):
    result = compute_shared_drugs(all_data)
    shared = {d["drug_id"]: d for d in result["shared_drugs"]}
    assert "rituximab" in shared
    assert shared["rituximab"]["disease_count"] >= 3


# ── Unit: Shared Pathways ──────────────────────────────────────────────────


def test_compute_shared_pathways_returns_dict(all_data):
    result = compute_shared_pathways(all_data)
    assert "shared_pathways" in result


# ── Unit: Disease Similarity ───────────────────────────────────────────────


def test_compute_disease_similarity_returns_matrix(all_data):
    result = compute_disease_similarity(all_data)
    assert "ranked_pairs" in result
    assert "matrix" in result
    assert len(result["ranked_pairs"]) == 21  # 7 choose 2


def test_disease_similarity_sle_ra_highest(all_data):
    result = compute_disease_similarity(all_data)
    top = result["ranked_pairs"][0]
    assert top["disease_a"] == "ra"
    assert top["disease_b"] == "sle"
    assert top["overall_similarity"] > 0.1


# ── Unit: Multi-Disease Drug Scoring ───────────────────────────────────────


def test_score_multi_disease_drugs_returns_list(all_data):
    genes = compute_shared_genes(all_data)
    pathways = compute_shared_pathways(all_data)
    results = score_multi_disease_drugs(all_data, genes, pathways)
    assert len(results) > 50
    for d in results:
        for field in ["drug_id", "drug_name", "composite_score", "tier",
                       "disease_coverage", "target_centrality",
                       "pathway_breadth", "mechanistic_transferability", "novelty"]:
            assert field in d


def test_score_multi_disease_drugs_sorted(all_data):
    genes = compute_shared_genes(all_data)
    pathways = compute_shared_pathways(all_data)
    results = score_multi_disease_drugs(all_data, genes, pathways)
    for i in range(len(results) - 1):
        assert results[i]["composite_score"] >= results[i + 1]["composite_score"]


def test_tier_assignment():
    assert "Tier 1" in _assign_tier(8.5)
    assert "Tier 2" in _assign_tier(6.5)
    assert "Tier 3" in _assign_tier(5.0)
    assert "Tier 4" in _assign_tier(3.0)


# ── Unit: Cross-Disease Repurposing ────────────────────────────────────────


def test_compute_cross_disease_repurposing_returns_list(all_data):
    result = compute_cross_disease_repurposing(all_data)
    assert len(result) > 0
    for r in result:
        assert "source_disease" in r
        assert "target_disease" in r
        assert "drug_id" in r
        assert "confidence" in r


# ── Integration: Full Pipeline ─────────────────────────────────────────────


def test_compute_cross_disease_analysis_returns_all_keys(analysis_results):
    for key in ["disease_summary", "shared_genes", "shared_drugs",
                "shared_pathways", "disease_similarity",
                "multi_disease_drugs", "cross_disease_repurposing",
                "total_diseases"]:
        assert key in analysis_results


def test_compute_cross_disease_analysis_7_diseases(analysis_results):
    assert analysis_results["total_diseases"] == 7


def test_compute_cross_disease_analysis_saves_json(tmp_path, monkeypatch):
    monkeypatch.setattr("cross_disease.analyzer.DATA_DIR", tmp_path)
    compute_cross_disease_analysis()
    json_path = tmp_path / "cross_disease_analysis.json"
    assert json_path.exists()
    data = json.loads(json_path.read_text())
    assert "disease_summary" in data


# ── Unit: CLI Print Functions ──────────────────────────────────────────────


def test_analyze_prints(capsys, analysis_results):
    analyze(analysis_results)
    captured = capsys.readouterr()
    assert "CROSS-DISEASE DRUG REPURPOSING" in captured.out
    assert "Diseases analyzed: 7" in captured.out


def test_print_top_drugs_prints(capsys, analysis_results):
    print_top_drugs(analysis_results, top_n=5)
    captured = capsys.readouterr()
    assert "MULTI-DISEASE DRUG CANDIDATES" in captured.out
    assert "Score:" in captured.out


def test_print_repurposing_prints(capsys, analysis_results):
    print_repurposing(analysis_results, top_n=5)
    captured = capsys.readouterr()
    assert "CROSS-DISEASE REPURPOSING OPPORTUNITIES" in captured.out


# ── Report ─────────────────────────────────────────────────────────────────


def test_escape_html_cross_disease():
    from cross_disease.report import escape_html
    assert escape_html("<script>") == "&lt;script&gt;"
    assert escape_html(None) == ""
    assert escape_html("AT&T") == "AT&amp;T"


@pytest.mark.slow
def test_generate_html_report(analysis_results):
    from cross_disease.report import generate_html_report

    path = generate_html_report(analysis_results)
    assert "report.html" in path
    assert Path(path).exists()
    Path(path).unlink(missing_ok=True)


# ── CLI Integration ────────────────────────────────────────────────────────


@pytest.mark.slow
def test_cross_disease_cli_help():
    import subprocess

    result = subprocess.run(
        [sys.executable, "main.py", "cross-disease", "--help"],
        capture_output=True,
        text=True, encoding="utf-8", errors="replace",
        cwd=str(Path(__file__).parent.parent),
    )
    assert result.returncode == 0
    assert "cross-disease" in result.stdout.lower()


@pytest.mark.slow
def test_cross_disease_cli_run():
    import subprocess

    result = subprocess.run(
        [sys.executable, "main.py", "cross-disease", "--top", "5"],
        capture_output=True,
        text=True, encoding="utf-8", errors="replace",
        cwd=str(Path(__file__).parent.parent),
    )
    assert result.returncode == 0
    assert "CROSS-DISEASE" in result.stdout
