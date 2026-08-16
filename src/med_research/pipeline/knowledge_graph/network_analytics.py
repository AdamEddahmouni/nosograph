"""Multi-Disease Knowledge Graph Network Topology & Cross-Talk Engine.

Generates merged subgraphs across multiple disease cohorts, identifying shared target hubs,
drug repurposing bridges, and pathway cross-talk with Cytoscape-compatible element structures.
"""

from __future__ import annotations

from typing import Any

from med_research.diseases.base import Disease
from med_research.pipeline.knowledge_graph.config import load_drugs, load_genes


def build_multi_disease_network(
    disease_ids: list[str],
    include_shared_only: bool = False,
    min_degree: int = 1,
) -> dict[str, Any]:
    """Construct a merged Cytoscape-compatible graph across multiple disease cohorts.

    Identifies shared target genes, repurposing drug bridges, and pathway overlaps.
    """
    if not disease_ids:
        disease_ids = ["sle", "ra", "ms", "ibd"]

    nodes_map: dict[str, dict[str, Any]] = {}
    edges_map: dict[str, dict[str, Any]] = {}
    disease_gene_map: dict[str, set[str]] = {}
    disease_drug_map: dict[str, set[str]] = {}

    for d_id in disease_ids:
        try:
            d = Disease(d_id)
            d_name = d.name
        except Exception:
            d_name = d_id.replace("_", " ").title()

        # Add disease root node
        d_node_id = f"disease:{d_id}"
        nodes_map[d_node_id] = {
            "data": {
                "id": d_node_id,
                "label": d_name,
                "type": "disease",
                "disease_id": d_id,
                "color": "#f43f5e",
                "shape": "star",
                "size": 45,
            }
        }

        # Load genes
        try:
            genes_data = load_genes(d_id)
            genes = genes_data.get("genes", [])
            gene_ids = set()
            for g in genes:
                gid = g.get("id") or g.get("gene_id") or g.get("name")
                if not gid:
                    continue
                gene_ids.add(gid)
                g_node_id = f"gene:{gid}"
                if g_node_id not in nodes_map:
                    nodes_map[g_node_id] = {
                        "data": {
                            "id": g_node_id,
                            "label": g.get("name", gid),
                            "type": "gene",
                            "associated_diseases": [d_id],
                            "color": "#4ade80",
                            "shape": "ellipse",
                            "size": 26,
                        }
                    }
                else:
                    if d_id not in nodes_map[g_node_id]["data"]["associated_diseases"]:
                        nodes_map[g_node_id]["data"]["associated_diseases"].append(d_id)

                # Edge from disease to gene
                edge_id = f"{d_node_id}->{g_node_id}"
                edges_map[edge_id] = {
                    "data": {
                        "id": edge_id,
                        "source": d_node_id,
                        "target": g_node_id,
                        "type": "ASSOCIATED_WITH",
                        "color": "#4ade80",
                        "weight": 1.0,
                    }
                }
            disease_gene_map[d_id] = gene_ids
        except Exception:
            disease_gene_map[d_id] = set()

        # Load drugs & relationships
        try:
            drugs_data = load_drugs(d_id)
            drugs = drugs_data.get("drugs", [])
            drug_ids = set()
            for dr in drugs:
                drid = dr.get("id") or dr.get("name")
                if not drid:
                    continue
                drug_ids.add(drid)
                dr_node_id = f"drug:{drid}"
                if dr_node_id not in nodes_map:
                    nodes_map[dr_node_id] = {
                        "data": {
                            "id": dr_node_id,
                            "label": dr.get("name", drid),
                            "type": "drug",
                            "associated_diseases": [d_id],
                            "mechanism": dr.get("mechanism", ""),
                            "color": "#60a5fa",
                            "shape": "round-rectangle",
                            "size": 30,
                        }
                    }
                else:
                    if d_id not in nodes_map[dr_node_id]["data"]["associated_diseases"]:
                        nodes_map[dr_node_id]["data"]["associated_diseases"].append(d_id)

                # Edge from drug to disease (indicated for)
                edge_id = f"{dr_node_id}->{d_node_id}"
                edges_map[edge_id] = {
                    "data": {
                        "id": edge_id,
                        "source": dr_node_id,
                        "target": d_node_id,
                        "type": "INDICATED_FOR",
                        "color": "#60a5fa",
                        "weight": 1.0,
                    }
                }

                # Drug -> Target Gene edges
                for target in dr.get("targets", []):
                    g_node_id = f"gene:{target}"
                    if g_node_id in nodes_map:
                        dt_edge = f"{dr_node_id}->{g_node_id}"
                        edges_map[dt_edge] = {
                            "data": {
                                "id": dt_edge,
                                "source": dr_node_id,
                                "target": g_node_id,
                                "type": "TARGETS",
                                "color": "#fbbf24",
                                "weight": 1.5,
                            }
                        }
            disease_drug_map[d_id] = drug_ids
        except Exception:
            disease_drug_map[d_id] = set()

    # Calculate degree centrality and identify shared hubs
    degrees: dict[str, int] = {nid: 0 for nid in nodes_map}
    for e in edges_map.values():
        src = e["data"]["source"]
        tgt = e["data"]["target"]
        if src in degrees:
            degrees[src] += 1
        if tgt in degrees:
            degrees[tgt] += 1

    # Find shared target genes across 2+ diseases
    shared_targets: list[dict[str, Any]] = []
    for nid, node in nodes_map.items():
        deg = degrees[nid]
        node["data"]["degree"] = deg
        node["data"]["size"] = max(24, min(65, 20 + deg * 4))

        if node["data"]["type"] == "gene":
            assocs = node["data"].get("associated_diseases", [])
            if len(assocs) >= 2:
                node["data"]["is_shared_hub"] = True
                node["data"]["color"] = "#e879f9"  # Magenta for multi-disease hub
                shared_targets.append({
                    "gene": node["data"]["label"],
                    "diseases": assocs,
                    "degree": deg,
                })
            else:
                node["data"]["is_shared_hub"] = False

        if node["data"]["type"] == "drug":
            assocs = node["data"].get("associated_diseases", [])
            if len(assocs) >= 2:
                node["data"]["is_repurposing_bridge"] = True
                node["data"]["color"] = "#38bdf8"
            else:
                node["data"]["is_repurposing_bridge"] = False

    # Filter by minimum degree or shared only if requested
    filtered_nodes = []
    for nid, node in nodes_map.items():
        if include_shared_only:
            if node["data"]["type"] == "disease" or node["data"].get("is_shared_hub") or node["data"].get("is_repurposing_bridge"):
                filtered_nodes.append(node)
        else:
            if degrees[nid] >= min_degree:
                filtered_nodes.append(node)

    valid_node_ids = {n["data"]["id"] for n in filtered_nodes}
    filtered_edges = [
        e for e in edges_map.values()
        if e["data"]["source"] in valid_node_ids and e["data"]["target"] in valid_node_ids
    ]

    return {
        "elements": {
            "nodes": filtered_nodes,
            "edges": filtered_edges,
        },
        "summary": {
            "disease_count": len(disease_ids),
            "total_nodes": len(filtered_nodes),
            "total_edges": len(filtered_edges),
            "shared_target_count": len(shared_targets),
            "shared_targets": sorted(shared_targets, key=lambda x: len(x["diseases"]), reverse=True),
        },
    }
