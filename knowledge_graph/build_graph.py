"""
Lupus Knowledge Graph Builder & Analyzer

Builds a heterogeneous knowledge graph connecting genes, drugs, pathways,
and Systemic Lupus Erythematosus (SLE) using NetworkX.

Usage:
    python build_graph.py              # Build and export graph as JSON
    python build_graph.py --analyze    # Build, analyze, and print insights
    python build_graph.py --export     # Export to web-compatible JSON
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import networkx as nx

# Fix Windows encoding for emoji output
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = Path(__file__).parent / "data"


def load_json(filename: str) -> dict:
    with open(DATA_DIR / filename, "r", encoding="utf-8") as f:
        return json.load(f)


def build_graph() -> nx.MultiDiGraph:
    """Build the full heterogeneous lupus knowledge graph."""
    G = nx.MultiDiGraph()

    # Add the central disease node
    G.add_node(
        "Lupus (SLE)",
        type="disease",
        label="Systemic Lupus Erythematosus",
        description="Chronic autoimmune disease characterized by autoantibody production, "
        "immune complex deposition, and multi-organ inflammation affecting ~5 million people worldwide.",
        prevalence="~5 million worldwide",
        female_to_male_ratio="9:1",
        peak_onset="15-45 years",
    )

    # --- Add Genes ---
    genes_data = load_json("genes.json")
    for gene in genes_data["genes"]:
        G.add_node(
            gene["id"],
            type="gene",
            label=gene["name"],
            description=gene["function"],
            chromosome=gene.get("chromosome", ""),
            lupus_evidence=gene.get("lupus_evidence", ""),
            odds_ratio=gene.get("odds_ratio"),
            category=gene.get("category", ""),
        )

    # --- Add Drugs ---
    drugs_data = load_json("drugs.json")
    for drug in drugs_data["drugs"]:
        G.add_node(
            drug["id"],
            type="drug",
            label=drug["name"],
            description=drug["mechanism"],
            drug_type=drug.get("type", ""),
            target=drug.get("target", ""),
            approval=drug.get("approval", ""),
            route=drug.get("route", ""),
            efficacy=drug.get("efficacy", ""),
            category=drug.get("category", ""),
        )

    # --- Add Pathways ---
    pathways_data = load_json("pathways.json")
    for pathway in pathways_data["pathways"]:
        G.add_node(
            pathway["id"],
            type="pathway",
            label=pathway["name"],
            description=pathway["description"],
        )

    # --- Add Relationships (Edges) ---
    rels_data = load_json("relationships.json")
    for rel in rels_data["relationships"]:
        G.add_edge(
            rel["source"],
            rel["target"],
            key=rel["type"],
            type=rel["type"],
            description=rel.get("description", ""),
        )

    return G


def analyze_graph(G: nx.MultiDiGraph):
    """Run comprehensive graph analysis and print findings."""
    print("=" * 70)
    print("🕸️  LUPUS KNOWLEDGE GRAPH ANALYSIS")
    print("=" * 70)

    # Node counts by type
    node_types = defaultdict(int)
    for _, data in G.nodes(data=True):
        node_types[data.get("type", "unknown")] += 1

    print("\n📊 Graph Overview:")
    print(f"   Total nodes: {G.number_of_nodes():,}")
    print(f"   Total edges: {G.number_of_edges():,}")
    print("\n   Node types:")
    for ntype, count in sorted(node_types.items()):
        print(f"     • {ntype}: {count}")

    edge_types = defaultdict(int)
    for _, _, data in G.edges(data=True):
        edge_types[data.get("type", "unknown")] += 1

    print("\n   Edge types:")
    for etype, count in sorted(edge_types.items()):
        print(f"     • {etype}: {count}")

    # --- Key Analyses ---

    print("\n" + "=" * 70)
    print("🎯 DRUG → TARGET ANALYSIS")
    print("=" * 70)
    for node, data in G.nodes(data=True):
        if data.get("type") == "drug":
            targets = [
                t for t in G.successors(node)
                if G.nodes[t].get("type") in ("gene", "pathway")
            ]
            if targets:
                target_info = []
                for t in targets:
                    tdata = G.nodes[t]
                    target_info.append(f"{tdata.get('label', t)} ({G.nodes[t].get('type')})")
                print(f"\n  💊 {data['label']}")
                print(f"     Mechanism: {data.get('description', 'N/A')[:120]}...")
                print(f"     Targets: {', '.join(target_info)}")

    print("\n" + "=" * 70)
    print("🧬 TOP GENE → DISEASE HUB ANALYSIS")
    print("=" * 70)
    # Find genes with the highest degree (most connected)
    gene_degrees = [
        (node, G.degree(node), G.nodes[node].get("label", node))
        for node, data in G.nodes(data=True)
        if data.get("type") == "gene"
    ]
    gene_degrees.sort(key=lambda x: x[1], reverse=True)

    print("\n  Genes most connected in the lupus network:")
    for node, deg, label in gene_degrees[:10]:
        categories = [G.nodes[n].get("type", "?") for n in G.neighbors(node)]
        neighbor_summary = ", ".join(f"{categories.count(c)} {c}" for c in set(categories))
        print(f"  • {label} (degree={deg}) — connected to: {neighbor_summary}")

    print("\n" + "=" * 70)
    print("🛤️  PATHWAY CONNECTIVITY")
    print("=" * 70)
    for node, data in G.nodes(data=True):
        if data.get("type") == "pathway":
            in_edges = list(G.in_edges(node, data=True))
            drugs_targeting = [
                G.nodes[u].get("label", u)
                for u, v, d in in_edges
                if G.nodes[u].get("type") in ("drug",)
            ]
            genes_in = [
                G.nodes[u].get("label", u)
                for u, v, d in in_edges
                if G.nodes[u].get("type") in ("gene",)
            ]
            print(f"\n  📍 {data['label']}")
            print(f"     Description: {data.get('description', 'N/A')[:150]}...")
            if drugs_targeting:
                print(f"     Drugs targeting this pathway: {', '.join(drugs_targeting)}")
            if genes_in:
                print(f"     Lupus-associated genes: {', '.join(genes_in)}")

    print("\n" + "=" * 70)
    print("💡 DRUG REPURPOSING INSIGHTS (Shortest Path Analysis)")
    print("=" * 70)
    # Find genes NOT directly targeted by any drug
    targeted_genes = set()
    for u, v, d in G.edges(data=True):
        if d.get("type") == "TARGETS" and G.nodes[v].get("type") == "gene":
            targeted_genes.add(v)

    untargeted_genes = [
        n for n, data in G.nodes(data=True)
        if data.get("type") == "gene" and n not in targeted_genes
    ]

    print(f"\n  🔬 {len(untargeted_genes)} lupus-associated genes with NO direct therapeutic agent:")
    for gene in untargeted_genes:
        gdata = G.nodes[gene]
        print(f"     • {gdata['label']} — {gdata.get('lupus_evidence', '')[:120]}...")

    print("\n" + "=" * 70)
    print("✅ Analysis complete.")
    print("=" * 70)


def export_for_web(G: nx.MultiDiGraph, output_path: str = None) -> dict:
    """Export the graph in a format suitable for Cytoscape.js visualization."""
    if output_path is None:
        output_path = Path(__file__).parent / "web" / "graph_data.json"

    elements = []

    # Export nodes
    for node_id, data in G.nodes(data=True):
        node_data = {
            "data": {
                "id": node_id,
                "label": data.get("label", node_id),
                "type": data.get("type", "unknown"),
                **{k: v for k, v in data.items() if k not in ("label", "type")},
            }
        }
        elements.append(node_data)

    # Export edges
    for u, v, key, data in G.edges(data=True, keys=True):
        edge_data = {
            "data": {
                "id": f"{u}--{key}--{v}",
                "source": u,
                "target": v,
                "type": data.get("type", "unknown"),
                "description": data.get("description", "")[:200],
            }
        }
        elements.append(edge_data)

    output = {"elements": elements}
    os.makedirs(Path(output_path).parent, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"✅ Graph exported to {output_path}")
    print(f"   Nodes: {sum(1 for e in elements if 'source' not in e['data'])}")
    print(f"   Edges: {sum(1 for e in elements if 'source' in e['data'])}")

    return output


def main():
    parser = argparse.ArgumentParser(
        description="Lupus Knowledge Graph Builder & Analyzer"
    )
    parser.add_argument(
        "--analyze", action="store_true", help="Run graph analysis after building"
    )
    parser.add_argument(
        "--export", action="store_true", help="Export graph for web visualization"
    )
    args = parser.parse_args()

    print("🔄 Building Lupus Knowledge Graph...")
    G = build_graph()
    print(f"✅ Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    if args.analyze:
        analyze_graph(G)

    if args.export or not args.analyze:
        export_for_web(G)

    return G


if __name__ == "__main__":
    G = main()
