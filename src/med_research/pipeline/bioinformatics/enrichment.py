"""
Lupus Pathway Enrichment Analysis

Performs gene set enrichment analysis on lupus-associated genes
using GSEApy (Enrichr web service).

Libraries:
  GO Biological Process, KEGG, Reactome, WikiPathways

Usage:
    python enrichment.py                    # Full analysis
    python enrichment.py --export-html      # Generate HTML report
"""

import argparse
import json
import os
from pathlib import Path

import networkx as nx

from med_research.cache import CacheManager
from med_research.exceptions import ExternalAPIError
from med_research.logging_config import get_logger
from med_research.pipeline.knowledge_graph.config import load_genes, load_pathways

logger = get_logger(__name__)
cache = CacheManager()

DATA_DIR = Path(__file__).parent / "data"
DR_DATA_DIR = Path(__file__).parent.parent / "drug_repurposing" / "data"

# ── GSEApy import ────────────────────────────────────────────────────────
try:
    import gseapy as gp

    GSEAPY_AVAILABLE = True
except ImportError:
    GSEAPY_AVAILABLE = False
    logger.warning("GSEApy not installed. Run: pip install gseapy")

# Gene set libraries to query
GENE_SET_LIBRARIES = [
    "GO_Biological_Process_2023",
    "KEGG_2021_Human",
    "Reactome_2022",
    "WikiPathway_2023_Human",
]


def load_kg_genes() -> dict:
    """Load lupus-associated genes from the knowledge graph, indexed by gene ID."""
    data = load_genes()
    return {g["id"]: g for g in data["genes"]}


def load_kg_graph() -> nx.MultiDiGraph:
    """Load the knowledge graph for gene targeting analysis."""
    from med_research.pipeline.knowledge_graph.builder import build_graph

    return build_graph()


def get_lupus_gene_list(
    genes: dict, G: nx.MultiDiGraph = None, untargeted_only: bool = False
) -> list:
    """
    Get the list of lupus gene symbols for enrichment analysis.

    Excludes drug-target-only genes (CD20, IMPDH, Calcineurin, Glucocorticoid Receptor)
    which are not lupus risk genes.

    Args:
        genes: Gene dictionary indexed by gene ID
        G: Knowledge graph (optional, for targeted gene detection)
        untargeted_only: If True, only return genes not targeted by any drug
    """
    # Drug target genes that are not lupus risk genes
    drug_target_exclusions = {
        "CD20",
        "IMPDH",
        "Calcineurin",
        "Glucocorticoid Receptor",
    }

    lupus_genes = []
    for gene_id, gene_info in genes.items():
        if gene_id in drug_target_exclusions:
            continue

        # If untargeted_only, filter out genes targeted by drugs
        if untargeted_only and G is not None:
            targeted = False
            for _u, v, d in G.edges(data=True):
                if d.get("type") == "TARGETS" and v == gene_id:
                    targeted = True
                    break
            if targeted:
                continue

        lupus_genes.append(
            {
                "gene_id": gene_id,
                "symbol": gene_id,
                "name": gene_info["name"],
                "category": gene_info.get("category", ""),
                "odds_ratio": gene_info.get("odds_ratio"),
                "chromosome": gene_info.get("chromosome", ""),
            }
        )

    return lupus_genes


def run_enrichment(
    gene_list: list,
    libraries: list = None,
    top_n: int = 15,
    use_cache: bool = True,
) -> dict:
    """
    Run pathway enrichment analysis using GSEApy Enrichr.

    Args:
        gene_list: List of gene dicts with 'symbol' field
        libraries: Gene set libraries to query
        top_n: Number of top terms to return per library
        use_cache: Load from cache if available (cache keyed by gene symbols)

    Returns:
        Dict with enrichment results keyed by library name
    """
    if libraries is None:
        libraries = list(GENE_SET_LIBRARIES)

    if not GSEAPY_AVAILABLE:
        logger.warning("GSEApy required. Run: pip install gseapy")
        return {}

    symbols = [g["symbol"] for g in gene_list if g["symbol"]]
    cache_key = ",".join(sorted(symbols))

    if use_cache:
        cached = cache.get("enrichment", cache_key)
        if cached is not None and cached.get("libraries") == libraries and cached.get("top_n") == top_n:
            logger.info("Loading enrichment results from cache...")
            logger.info("Genes: %s", ', '.join(symbols))
            return cached["results"]
        elif cached is not None:
            logger.warning("Cache key mismatch, re-running enrichment...")

    logger.info("Running enrichment analysis on %d genes...", len(symbols))
    logger.info("Genes: %s", ', '.join(symbols))

    results = {}
    for library in libraries:
        logger.info("  %s...", library)

        try:
            enr = gp.enrichr(
                gene_list=symbols,
                gene_sets=library,
                organism="human",
                outdir=None,
                no_plot=True,
                cutoff=0.05,
            )

            if enr.results is not None and not enr.results.empty:
                df = enr.results.head(top_n)
                results[library] = {
                    "library": library,
                    "terms": [],
                    "total_significant": len(enr.results),
                }
                for _, row in df.iterrows():
                    results[library]["terms"].append(
                        {
                            "term": row.get("Term", ""),
                            "overlap": str(row.get("Overlap", "")),
                            "p_value": float(row.get("P-value", 1.0)),
                            "adj_p_value": float(
                                row.get("Adjusted P-value", 1.0)
                            ),
                            "odds_ratio": float(row.get("Odds Ratio", 1.0)),
                            "combined_score": float(
                                row.get("Combined Score", 0)
                            ),
                            "genes": str(row.get("Genes", "")).split(";"),
                        }
                    )
                sig_count = len(
                    [
                        t
                        for t in results[library]["terms"]
                        if t["adj_p_value"] < 0.05
                    ]
                )
                logger.info("      %d significant terms (adj p < 0.05) out of %d total hits",
                            sig_count, results[library]['total_significant'])
            else:
                results[library] = {
                    "library": library,
                    "terms": [],
                    "total_significant": 0,
                }
                logger.info("      No results returned")

        except ExternalAPIError as e:
            logger.warning("      Enrichr API error: %s", e)
            results[library] = {
                "library": library,
                "terms": [],
                "total_significant": 0,
                "error": str(e),
            }
        except Exception as e:
            logger.warning("      Error: %s", e)
            results[library] = {
                "library": library,
                "terms": [],
                "total_significant": 0,
                "error": str(e),
            }

    cache.set("enrichment", cache_key, {
        "libraries": libraries,
        "top_n": top_n,
        "results": results,
    })
    logger.info("Cached enrichment results")

    return results


def cross_reference_with_kg_pathways(
    enrichment_results: dict, kg_pathways: dict
) -> dict:
    """
    Cross-reference enrichment terms with knowledge graph pathways.

    Matches enriched pathway terms against the 7 curated lupus pathways
    to validate that the enrichment analysis recovers known lupus biology.
    """
    matches = {}
    kg_pathway_names = {p["name"].lower(): p for p in kg_pathways["pathways"]}

    for library, result in enrichment_results.items():
        for term in result.get("terms", []):
            term_lower = term["term"].lower()
            for kg_name, kg_pathway in kg_pathway_names.items():
                # Check if enrichment term matches or overlaps with KG pathway
                kg_keywords = set(kg_name.lower().split())
                term_keywords = set(term_lower.split())

                # Match if significant keyword overlap OR direct substring match
                overlap = kg_keywords & term_keywords
                is_match = (
                    len(overlap) >= 2
                    or kg_name in term_lower
                    or (
                        len(overlap) >= 1
                        and any(
                            kw in term_lower
                            for kw in [
                                "interferon",
                                "ifn",
                                "b cell",
                                "t cell",
                                "nfkb",
                                "nf-κb",
                                "complement",
                                "toll",
                                "tlr",
                                "jak",
                                "stat",
                            ]
                        )
                    )
                )

                if is_match:
                    key = f"{kg_pathway['id']} ↔ {term['term'][:60]}"
                    matches.setdefault(key, []).append(
                        {
                            "kg_pathway_id": kg_pathway["id"],
                            "kg_pathway_name": kg_pathway["name"],
                            "enrichment_term": term["term"],
                            "library": library,
                            "adj_p_value": term["adj_p_value"],
                        }
                    )

    return matches


def analyze(enrichment_results: dict, gene_list: list, kg_matches: dict):
    """Log enrichment analysis summary."""
    logger.info("=" * 70)
    logger.info("PATHWAY ENRICHMENT ANALYSIS")
    logger.info("=" * 70)

    logger.info("  Genes analyzed: %d", len(gene_list))
    logger.info("  Gene set libraries queried: %d", len(enrichment_results))

    for library, result in enrichment_results.items():
        lib_name = result.get("library", library)
        n_terms = len(result.get("terms", []))
        n_sig = len(
            [t for t in result.get("terms", []) if t["adj_p_value"] < 0.05]
        )
        logger.info("  %s", lib_name)
        logger.info("    %d top terms (%d significant at adj p < 0.05)", n_terms, n_sig)

        for i, term in enumerate(result.get("terms", [])[:8], 1):
            sig_marker = "SIG" if term["adj_p_value"] < 0.05 else "   "
            logger.info("    %s %d. %s", sig_marker, i, term['term'][:70])
            logger.info("        P=%.2e | adj P=%.2e | OR=%.1f | Genes: %s",
                        term['p_value'], term['adj_p_value'], term['odds_ratio'],
                        ', '.join(term['genes'][:5]))

    if kg_matches:
        logger.info("  Cross-reference with KG pathways (%d matches):", len(kg_matches))
        for _key, matches_list in sorted(
            kg_matches.items(),
            key=lambda x: min(m["adj_p_value"] for m in x[1]),
        ):
            best = min(matches_list, key=lambda m: m["adj_p_value"])
            logger.info("    %s <-> %s (P=%.1e)",
                        best['kg_pathway_name'][:40], best['enrichment_term'][:50],
                        best['adj_p_value'])


def main():
    parser = argparse.ArgumentParser(
        description="Lupus Pathway Enrichment Analysis"
    )
    parser.add_argument(
        "--export-html", action="store_true", help="Generate HTML report"
    )
    parser.add_argument(
        "--untargeted-only",
        action="store_true",
        help="Restrict enrichment to untargeted lupus genes only",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Skip cache, re-run enrichment from GSEApy",
    )
    args = parser.parse_args()

    logger.info("Loading knowledge graph and gene data...")
    G = load_kg_graph()
    genes = load_kg_genes()
    logger.info("Loaded %d genes from knowledge graph", len(genes))

    logger.info("Preparing gene list...")
    gene_list = get_lupus_gene_list(
        genes, G, untargeted_only=args.untargeted_only
    )
    logger.info("Using %d genes for enrichment", len(gene_list))
    for g in gene_list:
        logger.debug("  - %s (%s) -- %s", g['symbol'], g['gene_id'], g['category'])

    logger.info("Running enrichment analysis...")
    enrichment_results = run_enrichment(
        gene_list, use_cache=not args.no_cache
    )

    logger.info("Cross-referencing with KG pathways...")
    kg_pathways = load_pathways()
    kg_matches = cross_reference_with_kg_pathways(
        enrichment_results, kg_pathways
    )

    analyze(enrichment_results, gene_list, kg_matches)

    # Save results
    os.makedirs(DATA_DIR, exist_ok=True)
    output = {
        "gene_list": gene_list,
        "enrichment_results": enrichment_results,
        "kg_pathway_matches": {
            k: v for k, v in kg_matches.items()
        },
    }
    out_path = DATA_DIR / "enrichment_results.json"
    out_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    logger.info("Results saved to %s", out_path)

    if args.export_html:
        from med_research.pipeline.bioinformatics.report import generate_bioinformatics_report

        report_path = generate_bioinformatics_report(
            enrichment_results, gene_list, kg_matches, None, None
        )
        logger.info("Report generated: %s", report_path)

    return enrichment_results


if __name__ == "__main__":
    enrichment_results = main()
