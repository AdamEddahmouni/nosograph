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
import sys
from collections import defaultdict
from pathlib import Path

import networkx as nx

sys.path.insert(0, str(Path(__file__).parent.parent))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = Path(__file__).parent / "data"


def load_graph():
    """Load the knowledge graph."""
    from med_research.pipeline.knowledge_graph.builder import build_graph
    return build_graph()


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


def compute_centrality(G=None, progress_callback=None) -> dict:
    """Compute all centrality metrics for every node.

    Returns dict with keys: degree, betweenness, eigenvector, closeness, pagerank.
    Each value is a dict of node_id -> score.
    """
    cb = progress_callback or (lambda p, m: None)
    if G is None:
        G = load_graph()

    UG = _to_undirected(G)

    cb(10, "Computing degree centrality...")
    degree = nx.degree_centrality(UG)

    cb(30, "Computing betweenness centrality...")
    betweenness = nx.betweenness_centrality(UG, weight=None)

    cb(50, "Computing eigenvector centrality...")
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

    cb(65, "Computing closeness centrality...")
    closeness = nx.closeness_centrality(UG)

    cb(75, "Computing PageRank...")
    pagerank = nx.pagerank(UG)

    cb(90, "Formatting results...")

    return {
        "degree": degree,
        "betweenness": betweenness,
        "eigenvector": eigenvector,
        "closeness": closeness,
        "pagerank": pagerank,
    }


def compute_bridge_nodes(G=None, centrality=None) -> list:
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


def compute_communities(G=None, progress_callback=None) -> dict:
    """Detect communities using Louvain (preferred) or greedy modularity.

    Returns dict with communities list and modularity score.
    """
    cb = progress_callback or (lambda p, m: None)
    if G is None:
        G = load_graph()

    UG = _to_undirected(G)

    cb(20, "Removing self-loops for community detection...")
    UG.remove_edges_from(nx.selfloop_edges(UG))

    cb(40, "Running community detection...")
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

    cb(70, "Classifying communities...")
    # Label each community by its dominant node type
    community_labels = []
    for i, comm in enumerate(communities):
        type_counts = defaultdict(int)
        labels = []
        for node_id in comm:
            ndata = G.nodes[node_id]
            ntype = ndata.get("type", "unknown")
            type_counts[ntype] += 1
            labels.append(ndata.get("label", node_id))
        dominant_type = max(type_counts, key=type_counts.get)
        community_labels.append({
            "id": i + 1,
            "size": len(comm),
            "dominant_type": dominant_type,
            "node_ids": comm,
            "node_labels": labels,
            "type_distribution": dict(type_counts),
        })

    cb(90, f"Found {len(communities)} communities (modularity={modularity:.3f})")

    return {
        "communities": community_labels,
        "modularity": round(modularity, 4),
        "n_communities": len(communities),
        "algorithm": algorithm_used,
    }


# ── Graph-Level Metrics ──────────────────────────────────────────────────


def compute_graph_metrics(G=None) -> dict:
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


def compute_all_metrics(progress_callback=None) -> dict:
    """Run all analyses and return combined results."""
    cb = progress_callback or (lambda p, m: None)

    cb(0, "Loading knowledge graph...")
    G = load_graph()

    cb(5, f"Graph loaded: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    # Graph metrics
    cb(10, "Computing graph-level metrics...")
    graph_metrics = compute_graph_metrics(G)

    # Centrality
    centrality = compute_centrality(G, progress_callback=lambda p, m: cb(15 + int(p * 0.35), m))

    # Bridge nodes
    cb(50, "Identifying bridge nodes...")
    bridge_nodes = compute_bridge_nodes(G, centrality)

    # Communities
    communities = compute_communities(G, progress_callback=lambda p, m: cb(55 + int(p * 0.35), m))

    cb(95, "Saving results...")
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Save centrality top-20 per metric
    centrality_summary = {}
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

    results = {
        "graph_metrics": graph_metrics,
        "centrality": centrality_summary,
        "bridge_nodes": bridge_nodes,
        "communities": communities,
    }

    output_path = DATA_DIR / "network_analysis.json"
    output_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")

    cb(100, f"Results saved to {output_path}")
    return results


# ── CLI ──────────────────────────────────────────────────────────────────


def print_analysis(results: dict):
    """Print formatted analysis summary."""
    gm = results["graph_metrics"]
    print("\n" + "=" * 75)
    print("🌐 NETWORK PHARMACOLOGY ANALYSIS")
    print("=" * 75)

    print("\n📊 Graph-Level Metrics:")
    print(f"   Nodes: {gm['n_nodes']}  |  Edges: {gm['n_edges']}")
    print(f"   Density: {gm['density']}  |  Components: {gm['n_components']}")
    print(f"   Diameter: {gm['diameter']}  |  Avg Path: {gm['avg_shortest_path']}")
    print(f"   Avg Clustering: {gm['avg_clustering']}  |  Assortativity: {gm['assortativity']}")

    com = results["communities"]
    print(f"\n🔗 Community Detection ({com['algorithm']}, modularity={com['modularity']}):")
    print(f"   {com['n_communities']} communities found")
    for c in com["communities"]:
        print(f"   Community {c['id']}: {c['size']} nodes (dominant: {c['dominant_type']})")

    print("\n🌉 Top 10 Bridge Nodes (betweenness centrality):")
    for i, b in enumerate(results["bridge_nodes"][:10], 1):
        print(f"   {i:2d}. {b['label']} ({b['type']}) — {b['betweenness']:.4f}")

    print("\n🎯 Top 5 by PageRank:")
    pr = results["centrality"].get("pagerank", [])
    for i, n in enumerate(pr[:5], 1):
        print(f"   {i}. {n['label']} ({n['type']}) — {n['score']:.4f}")

    print("\n⭐ Top 5 by Eigenvector Centrality:")
    ec = results["centrality"].get("eigenvector", [])
    for i, n in enumerate(ec[:5], 1):
        print(f"   {i}. {n['label']} ({n['type']}) — {n['score']:.4f}")


def main():
    parser = argparse.ArgumentParser(
        description="Network Pharmacology Hub — Deep analysis of the lupus knowledge graph"
    )
    parser.add_argument("--centrality", action="store_true", help="Show centrality only")
    parser.add_argument("--communities", action="store_true", help="Show communities only")
    parser.add_argument("--export-html", action="store_true", help="Generate HTML report")
    args = parser.parse_args()

    if args.centrality:
        G = load_graph()
        centrality = compute_centrality(G)
        print("\n🎯 CENTRALITY METRICS")
        for metric in ["degree", "betweenness", "eigenvector", "closeness", "pagerank"]:
            scores = centrality.get(metric, {})
            top5 = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:5]
            print(f"\n  {metric.upper()}:")
            for node, score in top5:
                label = G.nodes[node].get("label", node)
                print(f"    {label} — {score:.4f}")
        return

    if args.communities:
        communities = compute_communities()
        print(f"\n🔗 Communities (modularity={communities['modularity']}, {communities['n_communities']} total):")
        for c in communities["communities"]:
            print(f"\n  Community {c['id']} ({c['size']} nodes, dominant: {c['dominant_type']}):")
            for label in c["node_labels"][:8]:
                print(f"    • {label}")
            if len(c["node_labels"]) > 8:
                print(f"    ... and {len(c['node_labels']) - 8} more")
        return

    results = compute_all_metrics()
    print_analysis(results)

    if args.export_html:
        from med_research.pipeline.network_pharmacology.report import generate_html_report
        generate_html_report(results)
        print("\n✅ HTML report generated: network_pharmacology/report.html")

    return results


if __name__ == "__main__":
    main()
