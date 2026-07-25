"""Knowledge Graph Pydantic models."""

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class GraphNode(BaseModel):
    id: str
    label: str
    type: str  # gene, drug, pathway, disease
    description: Optional[str] = None
    category: Optional[str] = None
    chromosome: Optional[str] = None
    odds_ratio: Optional[float] = None
    drug_type: Optional[str] = None
    target: Optional[str] = None
    approval: Optional[str] = None


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str
    description: Optional[str] = None


class GraphData(BaseModel):
    elements: list[dict[str, Any]]


class GraphStats(BaseModel):
    total_nodes: int
    total_edges: int
    node_types: dict[str, int]
    edge_types: dict[str, int]
    untargeted_genes: list[dict[str, Any]]
    top_hub_genes: list[dict[str, Any]]


class ShortestPathRequest(BaseModel):
    source: str
    target: str


class ShortestPathResponse(BaseModel):
    path: list[str]
    length: int
    edges: list[dict[str, Any]]


class NeighborsResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    node_id: str
    neighbors: list[dict[str, Any]]
    degree: int = 0


class NodeDetailResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    type: str
    label: str
    incoming: list[dict[str, Any]] = []
    outgoing: list[dict[str, Any]] = []
    degree: int = 0


class SearchResponse(BaseModel):
    query: str
    count: int
    results: list[dict[str, Any]]


# ── Network Pharmacology Models ──────────────────────────────────────────


class CentralityNode(BaseModel):
    node_id: str
    label: str
    type: str
    score: float


class CentralityResponse(BaseModel):
    metric: str
    nodes: list[CentralityNode]
    total_nodes: int


class CommunityInfo(BaseModel):
    id: int
    size: int
    dominant_type: str
    node_ids: list[str] = []
    node_labels: list[str] = []
    type_distribution: dict[str, int] = {}


class CommunitiesResponse(BaseModel):
    communities: list[CommunityInfo]
    modularity: float
    n_communities: int
    algorithm: str
