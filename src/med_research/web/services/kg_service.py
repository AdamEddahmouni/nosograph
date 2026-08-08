"""Knowledge Graph service — wraps knowledge_graph registry adapter."""

from collections import defaultdict

import networkx as nx

from med_research.diseases.coverage import coverage_for_disease
from med_research.web.services.registry_service import (
    dispatch_sync_module,
    require_runnable_coverage,
)


def _kg_coverage_payload(disease_id: str) -> dict:
    core = coverage_for_disease(disease_id)
    return {
        **core.to_dict(),
        "module": "kg",
    }


def _load_graph(disease_id: str):
    """Build or load the knowledge graph via the registry dispatch path."""
    core = coverage_for_disease(disease_id)
    require_runnable_coverage(core, "knowledge_graph")
    return dispatch_sync_module("knowledge_graph", disease_id)


def get_graph_stats(disease_id: str = "sle") -> dict:
    """Return graph statistics including node/edge counts and untargeted genes."""
    coverage = _kg_coverage_payload(disease_id)
    G = _load_graph(disease_id)

    node_types = defaultdict(int)
    for _, data in G.nodes(data=True):
        node_types[data.get("type", "unknown")] += 1

    edge_types = defaultdict(int)
    for _, _, data in G.edges(data=True):
        edge_types[data.get("type", "unknown")] += 1

    # Untargeted genes
    targeted_genes = set()
    for _, v, d in G.edges(data=True):
        if d.get("type") == "TARGETS" and G.nodes[v].get("type") == "gene":
            targeted_genes.add(v)

    drug_target_exclusions = {"CD20", "IMPDH", "Calcineurin", "Glucocorticoid Receptor"}
    untargeted = []
    for node, data in G.nodes(data=True):
        if (
            data.get("type") == "gene"
            and node not in targeted_genes
            and node not in drug_target_exclusions
        ):
            untargeted.append({
                "id": node,
                "name": data.get("label", node),
                "category": data.get("category", ""),
                "function": data.get("description", ""),
                "odds_ratio": data.get("odds_ratio"),
                "chromosome": data.get("chromosome", ""),
            })

    # Top hub genes by degree
    gene_degrees = sorted(
        [
            {
                "id": node,
                "name": data.get("label", node),
                "degree": G.degree(node),
                "category": data.get("category", ""),
            }
            for node, data in G.nodes(data=True)
            if data.get("type") == "gene"
        ],
        key=lambda x: x["degree"],
        reverse=True,
    )[:10]

    return {
        "total_nodes": G.number_of_nodes(),
        "total_edges": G.number_of_edges(),
        "node_types": dict(node_types),
        "edge_types": dict(edge_types),
        "untargeted_genes": untargeted,
        "top_hub_genes": gene_degrees,
        "coverage": coverage,
        "status": "limited_coverage" if coverage.get("level") == "partial" else "ready",
    }


def get_graph_data(disease_id: str = "sle") -> dict:
    """Export graph data in Cytoscape.js format."""
    coverage = _kg_coverage_payload(disease_id)
    G = _load_graph(disease_id)

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

    return {
        "elements": elements,
        "coverage": coverage,
        "status": "limited_coverage" if coverage.get("level") == "partial" else "ready",
    }


def get_node_detail(node_id: str, disease_id: str = "sle") -> dict | None:
    """Get detailed information about a specific node."""
    G = _load_graph(disease_id)
    if node_id not in G:
        return None

    data = dict(G.nodes[node_id])
    data["id"] = node_id

    # In-edges and out-edges
    data["incoming"] = []
    for u, _, d in G.in_edges(node_id, data=True):
        data["incoming"].append({
            "source": u,
            "type": d.get("type", ""),
            "description": d.get("description", "")[:200],
        })

    data["outgoing"] = []
    for _, v, d in G.out_edges(node_id, data=True):
        data["outgoing"].append({
            "target": v,
            "type": d.get("type", ""),
            "description": d.get("description", "")[:200],
        })

    data["degree"] = G.degree(node_id)
    return data


def get_shortest_path(source: str, target: str, disease_id: str = "sle") -> dict | None:
    """Find the shortest path between two nodes."""
    G = _load_graph(disease_id)

    try:
        path = nx.shortest_path(G, source=source, target=target)
        edges = []
        for i in range(len(path) - 1):
            edge_data = G.get_edge_data(path[i], path[i + 1])
            if edge_data:
                for _, d in edge_data.items():
                    edges.append({
                        "source": path[i],
                        "target": path[i + 1],
                        "type": d.get("type", ""),
                        "description": d.get("description", "")[:200],
                    })
                    break
        return {"path": path, "length": len(path) - 1, "edges": edges}
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None


def get_neighbors(node_id: str, n_hops: int = 1, disease_id: str = "sle") -> dict | None:
    """Get neighbors of a node up to n_hops away."""
    G = _load_graph(disease_id)
    if node_id not in G:
        return None

    if n_hops == 1:
        neighbors = []
        for neighbor in G.neighbors(node_id):
            ndata = dict(G.nodes[neighbor])
            ndata["id"] = neighbor
            # Get edge type
            edge_types = []
            for _, _, d in G.edges(node_id, data=True):
                if _ in (neighbor,):
                    edge_types.append(d.get("type", ""))
            ndata["edge_types"] = edge_types
            neighbors.append(ndata)

        return {
            "node_id": node_id,
            "neighbors": neighbors,
            "degree": G.degree(node_id),
        }

    # Multi-hop: build ego graph
    nodes = set([node_id])
    for _ in range(n_hops):
        new_nodes = set()
        for n in nodes:
            new_nodes.update(G.neighbors(n))
        nodes.update(new_nodes)

    subgraph = G.subgraph(nodes)
    elements = []
    for n in subgraph.nodes():
        ndata = dict(subgraph.nodes[n])
        ndata["id"] = n
        elements.append(ndata)

    return {"node_id": node_id, "neighbors": elements, "subgraph_size": len(nodes)}


def search_nodes(query: str, disease_id: str = "sle") -> list[dict]:
    """Search nodes by label, ID, or description."""
    G = _load_graph(disease_id)

    query_lower = query.lower()
    results = []

    for node_id, data in G.nodes(data=True):
        label = data.get("label", "").lower()
        desc = data.get("description", "").lower()
        if query_lower in label or query_lower in node_id.lower() or query_lower in desc:
            results.append({
                "id": node_id,
                "label": data.get("label", node_id),
                "type": data.get("type", "unknown"),
                "description": data.get("description", "")[:200],
                "category": data.get("category", ""),
            })

    return results[:50]


# ── Network Pharmacology ────────────────────────────────────────────────


def run_centrality_analysis(
    metric: str = "betweenness", top_n: int = 15, disease_id: str = "sle"
) -> dict:
    """Compute centrality metrics via the network_pharmacology registry adapter."""
    return dispatch_sync_module(
        "network_pharmacology",
        disease_id,
        operation="centrality",
        metric=metric,
        top_n=top_n,
    )


def run_community_detection(disease_id: str = "sle") -> dict:
    """Detect communities in the selected disease knowledge graph."""
    return dispatch_sync_module(
        "network_pharmacology",
        disease_id,
        operation="communities",
    )
