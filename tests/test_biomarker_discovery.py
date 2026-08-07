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


# ── Disease threading ───────────────────────────────────────────────────


def test_module_output_path_per_disease(tmp_path, monkeypatch):
    from med_research.pipeline.biomarker_discovery import discover as d

    monkeypatch.setitem(d._MODULE_DATA_DIRS, "expression", tmp_path)
    # When a per-disease file exists, it wins over the shared file
    (tmp_path / "expression_correlations_ra.json").write_text("{}")
    path = d._module_output_path("expression", "expression_correlations.json", "ra")
    assert path.name == "expression_correlations_ra.json"


def test_module_output_path_shared_fallback(tmp_path, monkeypatch):
    """Missing per-disease files fall back to the shared module output."""
    from med_research.pipeline.biomarker_discovery import discover as d

    monkeypatch.setitem(d._MODULE_DATA_DIRS, "expression", tmp_path)
    (tmp_path / "expression_correlations.json").write_text("{}")
    path = d._module_output_path("expression", "expression_correlations.json", "sle")
    assert path.name == "expression_correlations.json"
    # Non-SLE also falls back to the shared file when no per-disease file exists
    path_ra = d._module_output_path("expression", "expression_correlations.json", "ra")
    assert path_ra.name == "expression_correlations.json"


def test_module_output_path_sle_prefers_per_disease(tmp_path, monkeypatch):
    from med_research.pipeline.biomarker_discovery import discover as d

    monkeypatch.setitem(d._MODULE_DATA_DIRS, "expression", tmp_path)
    (tmp_path / "expression_correlations_sle.json").write_text("{}")
    path = d._module_output_path("expression", "expression_correlations.json", "sle")
    assert path.name == "expression_correlations_sle.json"


def test_load_all_modules_reads_per_disease_files(tmp_path, monkeypatch):
    """Non-SLE biomarker reads per-disease module outputs when present."""
    import json

    from med_research.pipeline.biomarker_discovery import discover as d

    data_dir = tmp_path / "expression"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setitem(d._MODULE_DATA_DIRS, "expression", data_dir)
    (data_dir / "expression_correlations_ra.json").write_text(
        json.dumps({"drugs": [{"drug_id": "baricitinib", "composite_score": 8.0}]}))
    # A stale shared SLE file must NOT shadow the RA per-disease file
    (data_dir / "expression_correlations.json").write_text(
        json.dumps({"drugs": [{"drug_id": "sle_only", "composite_score": 9.0}]}))

    module_data = d.load_all_modules("ra")
    assert "baricitinib" in module_data["expression"]
    assert "sle_only" not in module_data["expression"]


def test_load_all_modules_reads_legacy_files(tmp_path, monkeypatch):
    """The CWD-relative path bug is fixed: files are resolved from module dirs."""
    import json

    from med_research.pipeline.biomarker_discovery import discover as d

    for module in ["expression", "cart", "repurpose", "safety", "synergy"]:
        data_dir = tmp_path / module
        data_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setitem(d._MODULE_DATA_DIRS, module, data_dir)

    (tmp_path / "expression" / "expression_correlations.json").write_text(
        json.dumps({"drugs": [{"drug_id": "baricitinib", "composite_score": 8.0}]}))
    (tmp_path / "cart" / "car_t_scores.json").write_text(
        json.dumps({"genes": [{"gene_id": "BTK", "composite_score": 9.0}]}))
    (tmp_path / "repurpose" / "candidates.json").write_text(
        json.dumps({"repurposing_candidates": [{"gene_id": "BTK"}]}))
    (tmp_path / "safety" / "profiles.json").write_text(
        json.dumps({"baricitinib": {"composite_safety_score": 7.0}}))
    (tmp_path / "synergy" / "synergy_results.json").write_text(
        json.dumps({"pairs": [{"drug_a_id": "d1"}]}))

    module_data = d.load_all_modules("sle")
    assert "baricitinib" in module_data["expression"]
    assert "BTK" in module_data["cart"]
    assert module_data["repurpose"][0]["gene_id"] == "BTK"
    assert module_data["safety"]["baricitinib"]["composite_safety_score"] == 7.0
    assert module_data["synergy"][0]["drug_a_id"] == "d1"


def test_build_gene_drug_target_map_threads_disease(monkeypatch):
    from med_research.pipeline.biomarker_discovery import discover as d

    captured = {}

    def fake_load_relationships(disease_id="sle"):
        captured["disease_id"] = disease_id
        return {"relationships": [
            {"type": "TARGETS", "source": "baricitinib", "target": "BTK"},
        ]}

    monkeypatch.setattr(d, "load_relationships", fake_load_relationships)
    monkeypatch.setattr(d, "_GENE_DRUG_TARGET_CACHE", {})
    result = d._build_gene_drug_target_map("ssc")
    assert captured["disease_id"] == "ssc"
    assert result["BTK"] == ["baricitinib"]


def test_compute_biomarker_matrix_threads_disease(monkeypatch):
    from med_research.pipeline.biomarker_discovery import discover as d

    captured = {}
    import networkx as nx

    def fake_build_graph(disease_id="sle"):
        captured["graph_disease"] = disease_id
        G = nx.MultiDiGraph()
        G.add_node("d1", type="disease")
        G.add_node("BTK", type="gene", name="BTK")
        return G

    def fake_load_all_modules(disease_id="sle"):
        captured["modules_disease"] = disease_id
        return {}

    import med_research.pipeline.knowledge_graph.builder as kg_builder
    monkeypatch.setattr(kg_builder, "build_graph", fake_build_graph)
    monkeypatch.setattr(d, "load_all_modules", fake_load_all_modules)
    monkeypatch.setattr(d, "_GENE_DRUG_TARGET_CACHE", {})

    results = d.compute_biomarker_matrix(disease_id="t1d")
    assert captured["graph_disease"] == "t1d"
    assert captured["modules_disease"] == "t1d"
    assert len(results) == 1
    assert results[0]["gene_id"] == "BTK"


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


def test_compute_biomarker_matrix_save_false_skips_write(tmp_path, monkeypatch):
    """save=False must not write the shared biomarker_matrix.json."""
    from med_research.pipeline.biomarker_discovery import discover as d

    monkeypatch.setattr(d, "DATA_DIR", tmp_path)
    compute_biomarker_matrix(save=False)
    assert not (tmp_path / "biomarker_matrix.json").exists()
    # And save=True still writes
    compute_biomarker_matrix(save=True)
    assert (tmp_path / "biomarker_matrix.json").exists()


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
