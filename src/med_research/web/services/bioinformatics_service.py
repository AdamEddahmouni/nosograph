"""Bioinformatics service — wraps GWAS, enrichment, PPI modules."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from med_research.pipeline.knowledge_graph.config import load_pathways
from med_research.web.config import (
    BIO_DATA_DIR,
    DR_DATA_DIR,
    USE_CACHE,
)
from med_research.web.dependencies import get_kg_genes, get_knowledge_graph, load_json

# ── GWAS ───────────────────────────────────────────────────────────────────

def run_gwas(
    max_studies: int = 30,
    no_cache: bool = False,
    progress_callback=None,
    disease_id: str = "sle",
) -> dict:
    """Run GWAS catalog annotation for a disease."""
    from med_research.pipeline.bioinformatics.gwas import (
        cross_reference_with_kg,
        disease_search_terms,
        extract_gene_associations,
        search_gwas_studies,
    )
    from med_research.rate_limiter import rate_limited_sleep

    genes = get_kg_genes(disease_id)
    cb = progress_callback or (lambda p, m: None)
    from med_research.diseases.coverage import module_coverage
    coverage = module_coverage(disease_id, "gwas", ("genes", "gwas_search_terms"))
    if not coverage.is_runnable:
        cb(100, "GWAS analysis blocked by incomplete disease coverage")
        return {"coverage": coverage.to_dict(), "status": "blocked", "top_hits": []}

    # Check cache (per-disease so results never bleed across diseases;
    # honor the legacy single-file SLE cache on first run)
    cache_path = BIO_DATA_DIR / f"gwas_cache_{disease_id}.json"
    if disease_id == "sle" and not cache_path.exists():
        legacy = BIO_DATA_DIR / "gwas_cache.json"
        if legacy.exists():
            cache_path = legacy
    if not no_cache and USE_CACHE and cache_path.exists():
        cached = load_json(cache_path)
        if cached.get("gwas_results"):
            cb(100, "Loaded GWAS results from cache")
            gwas_results = cached["gwas_results"]
            crossref = cached.get("crossref", {})
            response = _format_gwas_response(gwas_results, crossref, genes)
            response["coverage"] = coverage.to_dict()
            response["status"] = "ready"
            return response

    # Fetch from GWAS Catalog
    cb(10, "Fetching GWAS Catalog data…")
    all_studies = []
    for i, term in enumerate(disease_search_terms(disease_id)[:2]):
        studies = search_gwas_studies(term, max_results=max_studies // 2)
        all_studies.extend(studies)
        cb(10 + (i + 1) * 15, f"Fetched {len(studies)} studies for '{term}'")
        rate_limited_sleep(0.5)

    # Deduplicate
    cb(45, "Deduplicating studies…")
    seen = set()
    unique_studies = []
    for s in all_studies:
        acc = s.get("accessionId")
        if acc and acc not in seen:
            seen.add(acc)
            unique_studies.append(s)

    cb(55, f"Extracting gene associations from {len(unique_studies)} "
           f"unique studies…")
    gwas_results = extract_gene_associations(
        unique_studies, max_studies=max_studies, resolve_snps=True
    )

    cb(85, "Cross-referencing with knowledge graph…")
    crossref = cross_reference_with_kg(gwas_results, genes, disease_id=disease_id)

    cb(100, "GWAS analysis complete")
    response = _format_gwas_response(gwas_results, crossref, genes)
    response["coverage"] = coverage.to_dict()
    response["status"] = "ready"
    return response


def _format_gwas_response(gwas_results: dict, crossref: dict, genes: dict) -> dict:
    """Format GWAS results for API response."""
    gene_associations = gwas_results.get("gene_associations", {})
    top_hits = sorted(
        [
            {
                "gene": gene,
                "n_studies": info["n_studies"],
                "best_p_value": info["best_p_value"],
                "studies": info.get("studies", [])[:5],
            }
            for gene, info in gene_associations.items()
        ],
        key=lambda x: x["n_studies"],
        reverse=True,
    )[:20]

    return {
        "total_studies": gwas_results.get("total_studies_analyzed", 0),
        "total_associations": gwas_results.get("total_associations", 0),
        "unique_genes": len(gene_associations),
        "gene_associations": gene_associations,
        "crossref": crossref,
        "top_hits": top_hits,
    }


# ── Enrichment ─────────────────────────────────────────────────────────────

def run_enrichment(
    untargeted_only: bool = False,
    no_cache: bool = False,
    progress_callback=None,
    disease_id: str = "sle",
) -> dict:
    """Run pathway enrichment analysis for a disease."""
    from med_research.pipeline.bioinformatics.enrichment import (
        GENE_SET_LIBRARIES,
        cross_reference_with_kg_pathways,
        get_disease_gene_list,
    )
    from med_research.pipeline.bioinformatics.enrichment import (
        run_enrichment as do_enrichment,
    )

    G = get_knowledge_graph(disease_id)
    genes = get_kg_genes(disease_id)
    cb = progress_callback or (lambda p, m: None)
    from med_research.diseases.coverage import module_coverage
    coverage = module_coverage(disease_id, "enrichment", ("genes", "pathways"))
    if not coverage.is_runnable:
        cb(100, "Enrichment blocked by incomplete disease coverage")
        return {"coverage": coverage.to_dict(), "status": "blocked", "libraries": []}

    cb(10, "Compiling disease gene list…")
    gene_list = get_disease_gene_list(
        genes, G, untargeted_only=untargeted_only, disease_id=disease_id
    )

    cb(20, f"Running enrichment on {len(gene_list)} genes…")
    enrichment_results = do_enrichment(
        gene_list,
        libraries=list(GENE_SET_LIBRARIES),
        use_cache=not no_cache and USE_CACHE,
    )

    # Cross-reference with KG pathways
    cb(80, "Cross-referencing with knowledge graph pathways…")
    kg_pathways = load_pathways(disease_id)
    kg_matches = cross_reference_with_kg_pathways(
        enrichment_results, kg_pathways, disease_id=disease_id
    )

    cb(100, "Enrichment analysis complete")

    libraries = []
    for lib_name, result in enrichment_results.items():
        terms = []
        for t in result.get("terms", []):
            terms.append({
                "term": t["term"],
                "p_value": t["p_value"],
                "adj_p_value": t["adj_p_value"],
                "odds_ratio": t["odds_ratio"],
                "combined_score": t["combined_score"],
                "genes": t.get("genes", []),
                "overlap": t.get("overlap", ""),
            })
        libraries.append({
            "library": result.get("library", lib_name),
            "terms": terms,
            "total_significant": result.get("total_significant", 0),
        })

    return {
        "genes_analyzed": len(gene_list),
        "gene_list": [g["symbol"] for g in gene_list],
        "libraries": libraries,
        "kg_pathway_matches": {k: v for k, v in kg_matches.items()},
        "coverage": coverage.to_dict(),
        "status": "limited_coverage" if coverage.level == "partial" else "ready",
    }


# ── PPI ────────────────────────────────────────────────────────────────────

def run_ppi(
    confidence: float = 0.4,
    no_cache: bool = False,
    progress_callback=None,
    disease_id: str = "sle",
) -> dict:
    """Build PPI network and compute hub scores for a disease."""
    from med_research.pipeline.bioinformatics.ppi import (
        build_ppi_network,
        compute_hub_scores,
        cross_reference_with_candidates,
        get_gene_symbols,
    )

    genes = get_kg_genes(disease_id)
    candidates_data = load_json(DR_DATA_DIR / "candidates.json")
    candidates = candidates_data.get("repurposing_candidates", [])
    cb = progress_callback or (lambda p, m: None)

    cb(10, "Extracting gene symbols…")
    gene_symbols = get_gene_symbols(genes)

    cb(20, "Building PPI network from STRING database…")
    G_ppi = build_ppi_network(
        gene_symbols,
        confidence=confidence,
        use_cache=not no_cache and USE_CACHE,
    )

    from med_research.diseases.coverage import module_coverage
    coverage = module_coverage(disease_id, "ppi", ("genes",))
    if G_ppi.number_of_nodes() == 0:
        cb(100, "PPI network empty — no interactions found")
        return {
            "nodes": 0,
            "edges": 0,
            "seed_genes": len(gene_symbols),
            "confidence": confidence,
            "top_hubs": [],
            "hub_candidates": [],
            "hub_untargeted": [],
            "coverage": coverage.to_dict(),
            "status": "limited_coverage",
        }

    cb(60, f"Computing hub scores on {G_ppi.number_of_nodes()}-node network…")
    hub_scores = compute_hub_scores(G_ppi)

    cb(85, "Cross-referencing hubs with repurposing candidates…")
    crossref = cross_reference_with_candidates(hub_scores, G_ppi, genes, candidates)

    cb(100, "PPI analysis complete")

    top_hubs = []
    for h in hub_scores[:20]:
        top_hubs.append({
            "symbol": h["symbol"],
            "gene_id": h.get("gene_id"),
            "hub_score": h["hub_score"],
            "degree": h["degree"],
            "degree_centrality": h["degree_centrality"],
            "betweenness_centrality": h["betweenness_centrality"],
            "is_disease_gene": h["is_lupus_gene"],
            "is_lupus_gene": h["is_lupus_gene"],
            "is_seed": h["is_seed"],
        })

    return {
        "nodes": G_ppi.number_of_nodes(),
        "edges": G_ppi.number_of_edges(),
        "seed_genes": len(gene_symbols),
        "confidence": confidence,
        "top_hubs": top_hubs,
        "hub_candidates": crossref.get("hub_candidate_matches", []),
        "hub_untargeted": crossref.get("hub_untargeted", []),
        "coverage": coverage.to_dict(),
        "status": "limited_coverage" if coverage.level == "partial" else "ready",
    }
