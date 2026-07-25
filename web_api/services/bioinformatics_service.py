"""Bioinformatics service — wraps GWAS, enrichment, PPI modules."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from web_api.config import (
    BIO_DATA_DIR,
    DR_DATA_DIR,
    KG_DATA_DIR,
    USE_CACHE,
)
from web_api.dependencies import get_kg_genes, get_knowledge_graph, load_json

# ── GWAS ───────────────────────────────────────────────────────────────────

def run_gwas(max_studies: int = 30, no_cache: bool = False, progress_callback=None) -> dict:
    """Run GWAS catalog annotation."""
    import time

    from bioinformatics.gwas import (
        SLE_SEARCH_TERMS,
        cross_reference_with_kg,
        extract_gene_associations,
        search_gwas_studies,
    )

    genes = get_kg_genes()
    cb = progress_callback or (lambda p, m: None)

    # Check cache
    cache_path = BIO_DATA_DIR / "gwas_cache.json"
    if not no_cache and USE_CACHE and cache_path.exists():
        cached = load_json(cache_path)
        if cached.get("gwas_results"):
            cb(100, "Loaded GWAS results from cache")
            gwas_results = cached["gwas_results"]
            crossref = cached.get("crossref", {})
            return _format_gwas_response(gwas_results, crossref, genes)

    # Fetch from GWAS Catalog
    cb(10, "Fetching GWAS Catalog data…")
    all_studies = []
    for i, term in enumerate(SLE_SEARCH_TERMS[:2]):
        studies = search_gwas_studies(term, max_results=max_studies // 2)
        all_studies.extend(studies)
        cb(10 + (i + 1) * 15, f"Fetched {len(studies)} studies for '{term}'")
        time.sleep(0.5)

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
    crossref = cross_reference_with_kg(gwas_results, genes)

    cb(100, "GWAS analysis complete")
    return _format_gwas_response(gwas_results, crossref, genes)


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

def run_enrichment(untargeted_only: bool = False, no_cache: bool = False, progress_callback=None) -> dict:
    """Run pathway enrichment analysis."""
    from bioinformatics.enrichment import (
        GENE_SET_LIBRARIES,
        cross_reference_with_kg_pathways,
        get_lupus_gene_list,
    )
    from bioinformatics.enrichment import (
        run_enrichment as do_enrichment,
    )

    G = get_knowledge_graph()
    genes = get_kg_genes()
    cb = progress_callback or (lambda p, m: None)

    cb(10, "Compiling lupus gene list…")
    gene_list = get_lupus_gene_list(genes, G, untargeted_only=untargeted_only)

    cb(20, f"Running enrichment on {len(gene_list)} genes…")
    enrichment_results = do_enrichment(
        gene_list,
        libraries=list(GENE_SET_LIBRARIES),
        use_cache=not no_cache and USE_CACHE,
    )

    # Cross-reference with KG pathways
    cb(80, "Cross-referencing with knowledge graph pathways…")
    kg_pathways = json.loads((KG_DATA_DIR / "pathways.json").read_text(encoding="utf-8"))
    kg_matches = cross_reference_with_kg_pathways(enrichment_results, kg_pathways)

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
    }


# ── PPI ────────────────────────────────────────────────────────────────────

def run_ppi(confidence: float = 0.4, no_cache: bool = False, progress_callback=None) -> dict:
    """Build PPI network and compute hub scores."""
    from bioinformatics.ppi import (
        build_ppi_network,
        compute_hub_scores,
        cross_reference_with_candidates,
        get_gene_symbols,
    )

    genes = get_kg_genes()
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
    }
