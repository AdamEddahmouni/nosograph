"""Knowledge Graph Builder & Analyzer

Builds a heterogeneous graph connecting genes, drugs, pathways,
and a disease node using NetworkX. Supports multiple diseases via --disease flag.

Usage:
    python build_graph.py                          # Build SLE graph (default)
    python build_graph.py --disease ra             # Build RA graph
    python build_graph.py --disease ra --analyze   # Build + analyze
    python build_graph.py --disease sle --export   # Build + export for web
    python build_graph.py --list-diseases          # List available diseases
"""

import argparse
import json
import logging
import os
import sys
from collections import defaultdict
from pathlib import Path

import networkx as nx

logger = logging.getLogger(__name__)
from med_research.pipeline.knowledge_graph.config import (
    get_disease_profile,
    list_diseases,
    load_drugs,
    load_genes,
    load_pathways,
    load_relationships,
)

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def build_graph(disease_id: str = "sle") -> nx.MultiDiGraph:
    """Build a disease-specific heterogeneous knowledge graph."""
    G = nx.MultiDiGraph()
    profile = get_disease_profile(disease_id)

    disease_node_id = profile.get("kg_node_id", f"{profile['name']} ({profile['id'].upper()})")
    G.add_node(
        disease_node_id,
        type="disease",
        label=profile["name"],
        description=profile.get("description", ""),
        prevalence=profile.get("prevalence", ""),
        female_to_male_ratio=profile.get("female_to_male_ratio", ""),
        peak_onset=profile.get("peak_onset", ""),
        disease_id=disease_id,
    )

    genes_data = load_genes(disease_id)
    for gene in genes_data["genes"]:
        evidence_key = f"{disease_id}_evidence"
        evidence = gene.get(evidence_key) or gene.get("lupus_evidence") or gene.get("disease_evidence", "")
        G.add_node(
            gene["id"],
            type="gene",
            label=gene["name"],
            description=gene["function"],
            chromosome=gene.get("chromosome", ""),
            disease_evidence=evidence,
            lupus_evidence=evidence,
            odds_ratio=gene.get("odds_ratio"),
            category=gene.get("category", ""),
        )

    drugs_data = load_drugs(disease_id)
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

    pathways_data = load_pathways(disease_id)
    for pathway in pathways_data["pathways"]:
        G.add_node(
            pathway["id"],
            type="pathway",
            label=pathway["name"],
            description=pathway["description"],
        )

    rels_data = load_relationships(disease_id)
    for rel in rels_data["relationships"]:
        if rel["source"] in G and rel["target"] in G:
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
    disease_node = next((n for n, d in G.nodes(data=True) if d.get("type") == "disease"), None)
    disease_name = G.nodes[disease_node]["label"] if disease_node else "Disease"

    print("=" * 70)
    print(f"KNOWLEDGE GRAPH ANALYSIS: {disease_name}")
    print("=" * 70)

    node_types = defaultdict(int)
    for _, data in G.nodes(data=True):
        node_types[data.get("type", "unknown")] += 1

    print("\n  Graph Overview:")
    print(f"   Total nodes: {G.number_of_nodes():,}")
    print(f"   Total edges: {G.number_of_edges():,}")
    print("\n   Node types:")
    for ntype, count in sorted(node_types.items()):
        print(f"     \u2022 {ntype}: {count}")

    edge_types = defaultdict(int)
    for _, _, data in G.edges(data=True):
        edge_types[data.get("type", "unknown")] += 1

    print("\n   Edge types:")
    for etype, count in sorted(edge_types.items()):
        print(f"     \u2022 {etype}: {count}")

    print("\n" + "=" * 70)
    print("DRUG -> TARGET ANALYSIS")
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
                print(f"\n  {data['label']}")
                print(f"     Mechanism: {data.get('description', 'N/A')[:120]}...")
                print(f"     Targets: {', '.join(target_info)}")

    print("\n" + "=" * 70)
    print("TOP GENE HUB ANALYSIS")
    print("=" * 70)
    gene_degrees = [
        (node, G.degree(node), G.nodes[node].get("label", node))
        for node, data in G.nodes(data=True)
        if data.get("type") == "gene"
    ]
    gene_degrees.sort(key=lambda x: x[1], reverse=True)

    print(f"\n  Genes most connected in the {disease_name.lower()} network:")
    for node, deg, label in gene_degrees[:10]:
        categories = [G.nodes[n].get("type", "?") for n in G.neighbors(node)]
        neighbor_summary = ", ".join(f"{categories.count(c)} {c}" for c in set(categories))
        print(f"  \u2022 {label} (degree={deg}) \u2014 connected to: {neighbor_summary}")

    print("\n" + "=" * 70)
    print("PATHWAY CONNECTIVITY")
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
            print(f"\n  {data['label']}")
            print(f"     Description: {data.get('description', 'N/A')[:150]}...")
            if drugs_targeting:
                print(f"     Drugs targeting this pathway: {', '.join(drugs_targeting)}")
            if genes_in:
                print(f"     Associated genes: {', '.join(genes_in)}")

    print("\n" + "=" * 70)
    print("DRUG REPURPOSING INSIGHTS (Shortest Path Analysis)")
    print("=" * 70)
    targeted_genes = set()
    for u, v, d in G.edges(data=True):
        if d.get("type") == "TARGETS" and G.nodes[v].get("type") == "gene":
            targeted_genes.add(v)

    untargeted_genes = [
        n for n, data in G.nodes(data=True)
        if data.get("type") == "gene" and n not in targeted_genes
    ]

    print(f"\n  {len(untargeted_genes)} associated genes with NO direct therapeutic agent:")
    for gene in untargeted_genes:
        gdata = G.nodes[gene]
        print(f"     \u2022 {gdata['label']} \u2014 {gdata.get('disease_evidence', '')[:120]}...")

    print("\n" + "=" * 70)
    print("Analysis complete.")
    print("=" * 70)


def export_for_web(G: nx.MultiDiGraph, output_path: str = None, disease_id: str = "sle") -> dict:
    """Export the graph in a format suitable for Cytoscape.js visualization."""
    if output_path is None:
        output_path = Path(__file__).parent / "web" / f"graph_data_{disease_id}.json"

    elements = []

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

    output = {"elements": elements, "disease_id": disease_id}
    os.makedirs(Path(output_path).parent, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    logger.info(f"Graph exported to {output_path}")
    logger.info(f"   Nodes: {sum(1 for e in elements if 'source' not in e['data'])}")
    logger.info(f"   Edges: {sum(1 for e in elements if 'source' in e['data'])}")

    return output


def main():
    parser = argparse.ArgumentParser(description="Knowledge Graph Builder & Analyzer")
    parser.add_argument("--disease", type=str, default="sle",
                        help="Disease ID to build graph for (default: sle)")
    parser.add_argument("--analyze", action="store_true",
                        help="Run graph analysis after building")
    parser.add_argument("--export", action="store_true",
                        help="Export graph for web visualization")
    parser.add_argument("--list-diseases", action="store_true",
                        help="List available diseases and exit")
    args = parser.parse_args()

    if args.list_diseases:
        diseases = list_diseases()
        print("Available diseases:")
        for did, info in sorted(diseases.items()):
            print(f"  {did:6s} \u2014 {info['name']}")
        return None

    profile = get_disease_profile(args.disease)
    print(f"Building {profile['name']} Knowledge Graph...")
    G = build_graph(args.disease)
    print(f"Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    if args.analyze:
        analyze_graph(G)

    if args.export or not args.analyze:
        export_for_web(G, disease_id=args.disease)

    return G


if __name__ == "__main__":
    G = main()
