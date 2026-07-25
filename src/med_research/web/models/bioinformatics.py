"""Bioinformatics Pydantic models."""

from typing import Any, Optional

from pydantic import BaseModel

# ── GWAS ───────────────────────────────────────────────────────────────────

class GWASGeneHit(BaseModel):
    gene: str
    n_studies: int
    best_p_value: float
    studies: list[dict[str, Any]] = []


class GWASCrossReference(BaseModel):
    validated: dict[str, Any] = {}
    novel: dict[str, Any] = {}
    missing: dict[str, Any] = {}
    n_validated: int = 0
    n_novel: int = 0
    n_missing: int = 0


class GWASResponse(BaseModel):
    total_studies: int
    total_associations: int
    unique_genes: int
    gene_associations: dict[str, Any] = {}
    crossref: GWASCrossReference
    top_hits: list[GWASGeneHit]


class GWASRequest(BaseModel):
    max_studies: int = 30
    no_cache: bool = False


# ── Enrichment ─────────────────────────────────────────────────────────────

class EnrichmentTerm(BaseModel):
    term: str
    p_value: float
    adj_p_value: float
    odds_ratio: float
    combined_score: float
    genes: list[str]
    overlap: str = ""


class EnrichmentLibrary(BaseModel):
    library: str
    terms: list[EnrichmentTerm]
    total_significant: int = 0


class EnrichmentResponse(BaseModel):
    genes_analyzed: int
    gene_list: list[str]
    libraries: list[EnrichmentLibrary]
    kg_pathway_matches: dict[str, Any] = {}


class EnrichmentRequest(BaseModel):
    untargeted_only: bool = False
    no_cache: bool = False


# ── PPI ────────────────────────────────────────────────────────────────────

class HubProtein(BaseModel):
    symbol: str
    gene_id: Optional[str] = None
    hub_score: float
    degree: int
    degree_centrality: float
    betweenness_centrality: float
    is_lupus_gene: bool = False
    is_seed: bool = False


class PPINetworkResponse(BaseModel):
    nodes: int
    edges: int
    seed_genes: int
    confidence: float
    top_hubs: list[HubProtein]
    hub_candidates: list[dict[str, Any]]
    hub_untargeted: list[dict[str, Any]]


class PPIRequest(BaseModel):
    confidence: float = 0.4
    no_cache: bool = False


# ── Combined ───────────────────────────────────────────────────────────────

class CombinedBioResponse(BaseModel):
    gwas: Optional[GWASResponse] = None
    enrichment: Optional[EnrichmentResponse] = None
    ppi: Optional[PPINetworkResponse] = None
