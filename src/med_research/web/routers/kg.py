"""Knowledge Graph API router."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from med_research.web.models.kg import (
    CentralityResponse,
    CommunitiesResponse,
    GraphData,
    GraphStats,
    NeighborsResponse,
    NodeDetailResponse,
    SearchResponse,
    ShortestPathResponse,
)
from med_research.web.services.kg_service import (
    get_graph_data,
    get_graph_stats,
    get_neighbors,
    get_node_detail,
    get_shortest_path,
    run_centrality_analysis,
    run_community_detection,
    search_nodes,
)

router = APIRouter(prefix="/api/kg", tags=["Knowledge Graph"])


@router.get("/stats", response_model=GraphStats)
async def kg_stats(
    disease: str = Query("sle", description="Disease ID to build the graph for"),
) -> dict[str, Any]:
    """Get knowledge graph statistics (nodes, edges, untargeted genes, top hubs)."""
    return get_graph_stats(disease_id=disease)


@router.get("/graph", response_model=GraphData)
async def kg_graph(
    disease: str = Query("sle", description="Disease ID to build the graph for"),
) -> dict[str, Any]:
    """Get full graph data in Cytoscape.js format."""
    return get_graph_data(disease_id=disease)


@router.get("/search", response_model=SearchResponse)
async def kg_search(
    q: str = Query(..., min_length=1, max_length=500, description="Search query for nodes"),
    disease: str = Query("sle", description="Disease ID to search within"),
) -> dict[str, Any]:
    """Search nodes by label, ID, or description."""
    results = search_nodes(q, disease_id=disease)
    return {"query": q, "count": len(results), "results": results}


@router.get("/node/{node_id}", response_model=NodeDetailResponse)
async def kg_node(
    node_id: str,
    disease: str = Query("sle", description="Disease ID the graph was built for"),
) -> dict[str, Any]:
    """Get detailed information about a specific node."""
    detail = get_node_detail(node_id, disease_id=disease)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")
    return detail


@router.get("/path", response_model=ShortestPathResponse)
async def kg_shortest_path(
    source: str = Query(..., min_length=1, max_length=500, description="Source node ID"),
    target: str = Query(..., min_length=1, max_length=500, description="Target node ID"),
    disease: str = Query("sle", description="Disease ID the graph was built for"),
) -> dict[str, Any]:
    """Find the shortest path between two nodes."""
    result = get_shortest_path(source, target, disease_id=disease)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No path found between '{source}' and '{target}'",
        )
    return result


@router.get("/neighbors/{node_id}", response_model=NeighborsResponse)
async def kg_neighbors(
    node_id: str,
    hops: int = Query(1, ge=1, le=3, description="Number of hops (1-3)"),
    disease: str = Query("sle", description="Disease ID the graph was built for"),
) -> dict[str, Any]:
    """Get neighbors of a node."""
    result = get_neighbors(node_id, n_hops=hops, disease_id=disease)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")
    return result


# ── Network Pharmacology ────────────────────────────────────────────────


@router.get("/centrality", response_model=CentralityResponse)
async def kg_centrality(
    metric: str = Query("betweenness", min_length=1, max_length=50, description="Centrality metric: degree, betweenness, eigenvector, closeness, pagerank"),
    top_n: int = Query(15, ge=1, le=50, description="Number of top nodes"),
    disease: str = Query("sle", description="Disease ID"),
) -> dict[str, Any]:
    """Get centrality metrics for the selected disease graph."""
    return run_centrality_analysis(metric=metric, top_n=top_n, disease_id=disease)


@router.get("/communities", response_model=CommunitiesResponse)
async def kg_communities(disease: str = Query("sle", description="Disease ID")) -> dict[str, Any]:
    """Detect communities in the selected disease knowledge graph."""
    return run_community_detection(disease_id=disease)
