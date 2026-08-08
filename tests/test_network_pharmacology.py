"""
Tests for the Network Pharmacology Hub module.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from med_research.pipeline.network_pharmacology.analyzer import (
    compute_all_metrics,
    compute_bridge_nodes,
    compute_centrality,
    compute_communities,
    compute_graph_metrics,
    load_graph,
)
from med_research.pipeline.network_pharmacology.report import escape_html, generate_html_report

# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def graph():
    return load_graph()


# ── Unit: Graph Metrics ───────────────────────────────────────────────────


def test_compute_graph_metrics(graph):
    metrics = compute_graph_metrics(graph)
    assert metrics["n_nodes"] >= 72
    assert metrics["n_edges"] > 0
    assert 0 < metrics["density"] < 1
    assert metrics["n_components"] >= 1
    assert metrics["diameter"] > 0
    assert isinstance(metrics["avg_clustering"], float)


def test_compute_graph_metrics_assortativity(graph):
    metrics = compute_graph_metrics(graph)
    assert -1.0 <= metrics["assortativity"] <= 1.0


# ── Unit: Centrality ─────────────────────────────────────────────────────


def test_compute_centrality_has_all_metrics(graph):
    centrality = compute_centrality(graph)
    assert "degree" in centrality
    assert "betweenness" in centrality
    assert "closeness" in centrality
    assert "pagerank" in centrality
    assert "eigenvector" in centrality


def test_compute_centrality_degree_range(graph):
    centrality = compute_centrality(graph)
    for _node, score in centrality["degree"].items():
        assert 0.0 <= score <= 1.0


def test_compute_centrality_betweenness_range(graph):
    centrality = compute_centrality(graph)
    for _node, score in centrality["betweenness"].items():
        assert 0.0 <= score <= 1.0


def test_compute_centrality_pagerank_range(graph):
    centrality = compute_centrality(graph)
    for _node, score in centrality["pagerank"].items():
        assert score > 0


# ── Unit: Bridge Nodes ───────────────────────────────────────────────────


def test_compute_bridge_nodes(graph):
    centrality = compute_centrality(graph)
    bridges = compute_bridge_nodes(graph, centrality)
    assert len(bridges) == 20
    assert bridges[0]["betweenness"] >= bridges[-1]["betweenness"]
    for b in bridges:
        assert "node_id" in b
        assert "label" in b
        assert "type" in b
        assert "betweenness" in b


# ── Unit: Community Detection ────────────────────────────────────────────


def test_compute_communities(graph):
    communities = compute_communities(graph)
    assert communities["n_communities"] >= 2
    assert 0 < communities["modularity"] <= 1.0
    assert len(communities["communities"]) == communities["n_communities"]

    for c in communities["communities"]:
        assert c["size"] > 0
        assert c["dominant_type"] in ("gene", "drug", "pathway", "disease")
        assert "node_ids" in c


# ── Integration: Full Analysis ───────────────────────────────────────────


def test_compute_all_metrics_has_all_sections():
    results = compute_all_metrics()
    assert "graph_metrics" in results
    assert "centrality" in results
    assert "bridge_nodes" in results
    assert "communities" in results


def test_compute_all_metrics_centrality_summary():
    results = compute_all_metrics()
    centrality = results["centrality"]
    for metric in ["degree", "betweenness", "eigenvector", "closeness", "pagerank"]:
        assert metric in centrality
        assert len(centrality[metric]) > 0


@pytest.mark.slow
def test_compute_all_metrics_saves_json(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "med_research.pipeline.network_pharmacology.analyzer.DATA_DIR",
        tmp_path,
    )
    compute_all_metrics()
    json_path = tmp_path / "network_analysis.json"
    assert json_path.exists()
    data = json.loads(json_path.read_text())
    assert "graph_metrics" in data
    assert "communities" in data


# ── Report ───────────────────────────────────────────────────────────────


def test_escape_html_network():
    assert escape_html("<br>") == "&lt;br&gt;"
    assert escape_html(None) == ""


@pytest.mark.slow
def test_generate_html_report():
    results = compute_all_metrics()
    path = generate_html_report(results)
    assert "report.html" in path
    assert Path(path).exists()
    # Clean up to avoid cluttering source tree
    Path(path).unlink(missing_ok=True)


# ── API Service ──────────────────────────────────────────────────────────


@pytest.mark.slow
def test_run_centrality_analysis():
    from med_research.web.services.kg_service import run_centrality_analysis

    result = run_centrality_analysis(metric="betweenness", top_n=10)
    assert result["metric"] == "betweenness"
    assert len(result["nodes"]) == 10
    assert result["nodes"][0]["score"] > 0


@pytest.mark.slow
def test_run_community_detection():
    from med_research.web.services.kg_service import run_community_detection

    result = run_community_detection()
    assert result["n_communities"] >= 2
    assert "communities" in result
    assert result["modularity"] > 0


# ── CLI Integration ──────────────────────────────────────────────────────


@pytest.mark.slow
def test_network_cli_help():
    from tests.cli_helpers import cli_help_output

    help_text = cli_help_output("network", "--help")
    assert "network" in help_text.lower()
