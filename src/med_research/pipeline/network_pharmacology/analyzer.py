"""
Network Pharmacology Analysis Engine

Deep network analysis on the lupus knowledge graph:
  - Centrality: degree, betweenness, eigenvector, closeness, PageRank
  - Community detection: Louvain / greedy modularity
  - Bridge nodes: nodes connecting communities
  - Graph-level metrics: density, diameter, clustering coefficient

Usage:
    python network_pharmacology/analyzer.py              # Full analysis
    python network_pharmacology/analyzer.py --centrality # Centrality only
    python network_pharmacology/analyzer.py --export-html # Generate report
"""

import argparse
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, cast

import networkx as nx

from med_research.pipeline.progress import StandardProgress, _tick, cli_progress
from med_research.pipeline.results import (
    BridgeNode,
    CentralityEntry,
    CommunitiesResult,
    CommunityInfo,
    GraphMetrics,
    NetworkAnalysis,
)

sys.path.insert(0, str(Path(__file__).parent.parent))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

DATA_DIR = Path(__file__).parent / "data"

logger = logging.getLogger(__name__)
last_coverage = None


def load_graph(disease_id: str = "sle") -> Any:
    """Load the knowledge graph for the requested disease."""
    from med_research.pipeline.knowledge_graph.builder import build_graph
    return build_graph(disease_id)


def _to_undirected(G):
    """Convert MultiDiGraph to undirected Graph for algorithms that require it."""
    UG = nx.Graph()
    for u, v, data in G.edges(data=True):
        t = data.get("type", "unknown")
        if UG.has_edge(u, v):
            UG[u][v]["types"] = UG[u][v].get("types", set()) | {t}
        else:
            UG.add_edge(u, v, types={t})
    # Also add all nodes
    UG.add_nodes_from(G.nodes(data=True))
    return UG


# ── Centrality Metrics ───────────────────────────────────────────────────


def compute_centrality(
    G: Any = None,
    progress_callback: StandardProgress | None = None,
) -> dict[str, dict[str, float]]:
    """Compute all centrality metrics for every node.

    Returns dict with keys: degree, betweenness, eigenvector, closeness, pagerank.
    Each value is a dict of node_id -> score.
    """
    if G is None:
        G = load_graph()

    UG = _to_undirected(G)

    _tick(progress_callback, "degree centrality", 1, 5)
    degree = nx.degree_centrality(UG)

    _tick(progress_callback, "betweenness centrality", 2, 5)
    betweenness = nx.betweenness_centrality(UG, weight=None)

    _tick(progress_callback, "eigenvector centrality", 3, 5)
    eigenvector = {}
    try:
        # Eigenvector centrality requires a connected graph
        if UG.number_of_nodes() > 0:
            # Use largest connected component
            components = list(nx.connected_components(UG))
            largest = max(components, key=len)
            sub_ug = UG.subgraph(largest).copy()
            if sub_ug.number_of_nodes() > 1:
                try:
                    eigenvector = nx.eigenvector_centrality_numpy(sub_ug, max_iter=200)
                except (ImportError, nx.NetworkXError, nx.AmbiguousSolution):
                    try:
                        eigenvector = nx.eigenvector_centrality(sub_ug, max_iter=200)
                    except (nx.NetworkXError, nx.AmbiguousSolution):
                        eigenvector = {}
    except nx.NetworkXError:
        eigenvector = {}

    _tick(progress_callback, "closeness centrality", 4, 5)
    closeness = nx.closeness_centrality(UG)

    _tick(progress_callback, "pagerank", 5, 5)
    pagerank = nx.pagerank(UG)

    return {
        "degree": degree,
        "betweenness": betweenness,
        "eigenvector": eigenvector,
        "closeness": closeness,
        "pagerank": pagerank,
    }


def compute_bridge_nodes(G: Any = None, centrality: Any = None) -> list[BridgeNode]:
    """Identify bridge nodes: top nodes by betweenness centrality."""
    if G is None:
        G = load_graph()
    if centrality is None:
        centrality = compute_centrality(G)
    betweenness = centrality["betweenness"]
    sorted_nodes = sorted(betweenness.items(), key=lambda x: x[1], reverse=True)
    return [
        {
            "node_id": node,
            "betweenness": round(score, 4),
            "type": G.nodes[node].get("type", "unknown"),
            "label": G.nodes[node].get("label", node),
        }
        for node, score in sorted_nodes[:20]
    ]


# ── Community Detection ──────────────────────────────────────────────────


def compute_communities(
    G: Any = None,
    progress_callback: StandardProgress | None = None,
) -> CommunitiesResult:
    """Detect communities using Louvain (preferred) or greedy modularity.

    Returns dict with communities list and modularity score.
    """
    if G is None:
        G = load_graph()

    UG = _to_undirected(G)

    _tick(progress_callback, "community detection", 1, 4)
    UG.remove_edges_from(nx.selfloop_edges(UG))

    _tick(progress_callback, "community detection", 2, 4)
    communities = []
    modularity = 0.0

    algorithm_used = "greedy_modularity"
    try:
        # NetworkX 3.x Louvain
        from networkx.algorithms.community import louvain_communities
        raw_communities = louvain_communities(UG, seed=42)
        communities = [sorted(list(c)) for c in raw_communities]
        modularity = nx.community.modularity(UG, raw_communities)
        algorithm_used = "louvain"
    except (ImportError, AttributeError):
        # Fallback to greedy modularity (always available)
        from networkx.algorithms.community import greedy_modularity_communities
        raw_communities = greedy_modularity_communities(UG)
        communities = [sorted(list(c)) for c in raw_communities]
        modularity = nx.community.modularity(UG, raw_communities)

    _tick(progress_callback, "classifying communities", 3, 4)
    # Label each community by its dominant node type
    community_labels: list[CommunityInfo] = []
    for i, comm in enumerate(communities):
        type_counts: dict[str, int] = defaultdict(int)
        labels = []
        for node_id in comm:
            ndata = G.nodes[node_id]
            ntype = ndata.get("type", "unknown")
            type_counts[ntype] += 1
            labels.append(ndata.get("label", node_id))
        dominant_type = max(type_counts, key=lambda t: type_counts.get(t, 0))
        community_labels.append({
            "id": i + 1,
            "size": len(comm),
            "dominant_type": dominant_type,
            "node_ids": comm,
            "node_labels": labels,
            "type_distribution": dict(type_counts),
        })

    _tick(progress_callback, "community detection", 4, 4)

    return {
        "communities": community_labels,
        "modularity": round(modularity, 4),
        "n_communities": len(communities),
        "algorithm": algorithm_used,
    }


# ── Graph-Level Metrics ──────────────────────────────────────────────────


def compute_graph_metrics(G: Any = None) -> GraphMetrics:
    """Compute graph-level topological metrics."""
    if G is None:
        G = load_graph()
    UG = _to_undirected(G)

    density = nx.density(UG)
    n_nodes = UG.number_of_nodes()
    n_edges = UG.number_of_edges()

    # Average clustering coefficient
    try:
        avg_clustering = nx.average_clustering(UG)
    except ZeroDivisionError:
        avg_clustering = 0.0

    # Connected components
    if nx.is_connected(UG):
        n_components = 1
        diameter = nx.diameter(UG)
        avg_shortest_path = nx.average_shortest_path_length(UG)
    else:
        components = list(nx.connected_components(UG))
        n_components = len(components)
        largest_cc = UG.subgraph(max(components, key=len))
        try:
            diameter = nx.diameter(largest_cc)
            avg_shortest_path = nx.average_shortest_path_length(largest_cc)
        except nx.NetworkXError:
            diameter = 0
            avg_shortest_path = 0.0

    # Degree assortativity
    try:
        assortativity = nx.degree_assortativity_coefficient(UG)
    except Exception:
        assortativity = 0.0

    return {
        "n_nodes": n_nodes,
        "n_edges": n_edges,
        "density": round(density, 4),
        "n_components": n_components,
        "diameter": diameter,
        "avg_shortest_path": round(avg_shortest_path, 2),
        "avg_clustering": round(avg_clustering, 4),
        "assortativity": round(assortativity, 4),
    }


# ── Combined ─────────────────────────────────────────────────────────────


def compute_all_metrics(
    progress_callback: StandardProgress | None = None,
    disease_id: str = "sle",
) -> NetworkAnalysis:
    """Run all analyses and return combined results."""
    from med_research.diseases.coverage import module_coverage

    global last_coverage
    coverage = module_coverage(
        disease_id, "network_pharm", ("genes", "relationships")
    )
    last_coverage = coverage
    if not coverage.is_runnable:
        _tick(progress_callback, "network pharmacology blocked", 1, 1)
        return {"coverage": coverage.to_dict(), "status": "blocked"}

    _tick(progress_callback, "loading knowledge graph", 1, 5)
    G = load_graph(disease_id)

    _tick(progress_callback, "graph metrics", 2, 5)
    graph_metrics = compute_graph_metrics(G)

    _tick(progress_callback, "centrality", 3, 5)
    centrality = compute_centrality(G, progress_callback=progress_callback)

    _tick(progress_callback, "bridge nodes", 4, 5)
    bridge_nodes = compute_bridge_nodes(G, centrality)

    communities = compute_communities(G, progress_callback=progress_callback)

    _tick(progress_callback, "saving results", 4, 5)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Save centrality top-20 per metric
    centrality_summary: dict[str, list[CentralityEntry]] = {}
    for metric, scores in centrality.items():
        top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:20]
        centrality_summary[metric] = [
            {
                "node_id": node,
                "score": round(score, 4),
                "label": G.nodes[node].get("label", node),
                "type": G.nodes[node].get("type", "unknown"),
            }
            for node, score in top
        ]

    results: NetworkAnalysis = {
        "graph_metrics": graph_metrics,
        "centrality": centrality_summary,
        "bridge_nodes": bridge_nodes,
        "communities": communities,
        "disease_id": disease_id,
    }

    output_path = DATA_DIR / "network_analysis.json"
    output_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")

    _tick(progress_callback, "saving results", 5, 5)
    return results


# ── CLI ──────────────────────────────────────────────────────────────────


def print_analysis(results: NetworkAnalysis) -> None:
    """Print formatted analysis summary."""
    gm = results["graph_metrics"]
    logger.info("\n" + "=" * 75)
    logger.info("🌐 NETWORK PHARMACOLOGY ANALYSIS")
    logger.info("=" * 75)

    logger.info("\n📊 Graph-Level Metrics:")
    logger.info(f"   Nodes: {gm['n_nodes']}  |  Edges: {gm['n_edges']}")
    logger.info(f"   Density: {gm['density']}  |  Components: {gm['n_components']}")
    logger.info(f"   Diameter: {gm['diameter']}  |  Avg Path: {gm['avg_shortest_path']}")
    logger.info(f"   Avg Clustering: {gm['avg_clustering']}  |  Assortativity: {gm['assortativity']}")

    com = results["communities"]
    logger.info(f"\n🔗 Community Detection ({com['algorithm']}, modularity={com['modularity']}):")
    logger.info(f"   {com['n_communities']} communities found")
    for c in com["communities"]:
        logger.info(f"   Community {c['id']}: {c['size']} nodes (dominant: {c['dominant_type']})")

    logger.info("\n🌉 Top 10 Bridge Nodes (betweenness centrality):")
    for i, b in enumerate(results["bridge_nodes"][:10], 1):
        logger.info(f"   {i:2d}. {b['label']} ({b['type']}) — {b['betweenness']:.4f}")

    logger.info("\n🎯 Top 5 by PageRank:")
    pr = results["centrality"].get("pagerank", [])
    for i, n in enumerate(pr[:5], 1):
        logger.info(f"   {i}. {n['label']} ({n['type']}) — {n['score']:.4f}")

    logger.info("\n⭐ Top 5 by Eigenvector Centrality:")
    ec = results["centrality"].get("eigenvector", [])
    for i, n in enumerate(ec[:5], 1):
        logger.info(f"   {i}. {n['label']} ({n['type']}) — {n['score']:.4f}")


def main():
    parser = argparse.ArgumentParser(
        description="Network Pharmacology Hub — Deep analysis of the lupus knowledge graph"
    )
    parser.add_argument("--centrality", action="store_true", help="Show centrality only")
    parser.add_argument("--communities", action="store_true", help="Show communities only")
    parser.add_argument("--export-html", action="store_true", help="Generate HTML report")
    parser.add_argument("--disease", "-d", default="sle", help="Disease ID (default: sle)")
    args = parser.parse_args()

    if args.centrality:
        G = load_graph(args.disease)
        centrality = compute_centrality(G, progress_callback=cli_progress)
        logger.info("\n🎯 CENTRALITY METRICS")
        for metric in ["degree", "betweenness", "eigenvector", "closeness", "pagerank"]:
            scores = centrality.get(metric, {})
            top5 = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:5]
            logger.info(f"\n  {metric.upper()}:")
            for node, score in top5:
                label = G.nodes[node].get("label", node)
                logger.info(f"    {label} — {score:.4f}")
        return

    if args.communities:
        communities = compute_communities(
            G=load_graph(args.disease), progress_callback=cli_progress
        )
        logger.info(f"\n🔗 Communities (modularity={communities['modularity']}, {communities['n_communities']} total):")
        for c in communities["communities"]:
            logger.info(f"\n  Community {c['id']} ({c['size']} nodes, dominant: {c['dominant_type']}):")
            for label in c["node_labels"][:8]:
                logger.info(f"    • {label}")
            if len(c["node_labels"]) > 8:
                logger.info(f"    ... and {len(c['node_labels']) - 8} more")
        return

    results = compute_all_metrics(disease_id=args.disease, progress_callback=cli_progress)
    print_analysis(results)

    if args.export_html:
        from med_research.pipeline.network_pharmacology.report import generate_html_report
        from med_research.pipeline.provenance import build_provenance

        provenance = build_provenance(
            disease_id=args.disease,
            module="network_pharmacology",
            sources=["knowledge_graph"],
            cache_or_live="cache",
        )
        generate_html_report(
            cast(dict, results), disease_id=args.disease, provenance=provenance
        )
        logger.info("\n✅ HTML report generated: network_pharmacology/report.html")

    return results


if __name__ == "__main__":
    main()
