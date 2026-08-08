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
import sys
from pathlib import Path

import networkx as nx

sys.path.insert(0, str(Path(__file__).parent.parent))

import logging

from med_research.cache import NS_ENRICHMENT, cache_get, cache_set, load_legacy_json
from med_research.exceptions import ExternalAPIError, classify_api_error
from med_research.pipeline.knowledge_graph.config import load_genes, load_pathways

logger = logging.getLogger(__name__)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = Path(__file__).parent / "data"
LEGACY_ENRICHMENT_CACHE = DATA_DIR / "enrichment_cache.json"
DR_DATA_DIR = Path(__file__).parent.parent / "drug_repurposing" / "data"

# ── GSEApy import ────────────────────────────────────────────────────────
try:
    import gseapy as gp

    GSEAPY_AVAILABLE = True
except ImportError:
    GSEAPY_AVAILABLE = False
    logger.info(
        "⚠️  GSEApy not installed. Install with: pip install gseapy"
    )

# Gene set libraries to query
GENE_SET_LIBRARIES = [
    "GO_Biological_Process_2023",
    "KEGG_2021_Human",
    "Reactome_2022",
    "WikiPathway_2023_Human",
]


def load_kg_genes(disease_id: str = "sle") -> dict:
    """Load a disease's genes from the knowledge graph, indexed by gene ID."""
    data = load_genes(disease_id)
    return {g["id"]: g for g in data["genes"]}


def load_kg_graph(disease_id: str = "sle") -> nx.MultiDiGraph:
    """Load the knowledge graph for a disease for gene targeting analysis."""
    from med_research.pipeline.knowledge_graph.builder import build_graph

    return build_graph(disease_id)


def get_lupus_gene_list(
    genes: dict, G: nx.MultiDiGraph = None, untargeted_only: bool = False,
    disease_id: str = "sle",
) -> list:

    """Return the active disease's analyzable gene list.

    .. deprecated::
        Use :func:`get_disease_gene_list` instead. The name is retained for
        compatibility with existing callers.
    """
    import warnings

    warnings.warn(
        "get_lupus_gene_list() is deprecated; use get_disease_gene_list() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return get_disease_gene_list(genes, G, untargeted_only, disease_id)


def get_disease_gene_list(
    genes: dict, G: nx.MultiDiGraph = None, untargeted_only: bool = False,
    disease_id: str = "sle",
) -> list:
    """Return the active disease's analyzable gene list."""
    # Drug target genes that are not disease risk genes
    from med_research.diseases.base import Disease

    drug_target_exclusions = Disease(disease_id).get_drug_target_exclusions()

    disease_genes = []
    for gene_id, gene_info in genes.items():
        if gene_id in drug_target_exclusions:
            continue

        # If untargeted_only, filter out genes targeted by drugs
        if untargeted_only and G is not None:
            targeted = False
            for _, v, d in G.edges(data=True):
                if d.get("type") == "TARGETS" and v == gene_id:
                    targeted = True
                    break
            if targeted:
                continue

        disease_genes.append(
            {
                "gene_id": gene_id,
                "symbol": gene_id,
                "name": gene_info["name"],
                "category": gene_info.get("category", ""),
                "disease_evidence": Disease(disease_id).get_disease_evidence(gene_info),
                "odds_ratio": gene_info.get("odds_ratio"),
                "chromosome": gene_info.get("chromosome", ""),
            }
        )

    return disease_genes


def load_disease_gene_list(
    disease_id: str = "sle",
    untargeted_only: bool = False,
) -> list:
    """Load the active disease's analyzable gene list from the knowledge graph."""
    genes = load_kg_genes(disease_id)
    graph = load_kg_graph(disease_id) if untargeted_only else None
    return get_disease_gene_list(
        genes, graph, untargeted_only=untargeted_only, disease_id=disease_id
    )


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
        logger.info("❌ GSEApy required. Install: pip install gseapy")
        return {}

    symbols = [g["symbol"] for g in gene_list if g["symbol"]]
    cache_key = ",".join(sorted(symbols))
    libraries_key = json.dumps(libraries, sort_keys=True)
    cache_lookup_key = f"{cache_key}|||{libraries_key}|||{top_n}"

    cached = cache_get(NS_ENRICHMENT, cache_lookup_key, use_cache=use_cache)
    if cached is None and use_cache:
        legacy = load_legacy_json(LEGACY_ENRICHMENT_CACHE)
        if (
            legacy
            and legacy.get("cache_key") == cache_key
            and legacy.get("libraries") == libraries
            and legacy.get("top_n") == top_n
        ):
            cached = legacy.get("results")
            if cached is not None:
                cache_set(
                    NS_ENRICHMENT,
                    cache_lookup_key,
                    cached,
                    use_cache=True,
                )

    if cached is not None:
        logger.info("📦 Loading enrichment results from cache...")
        logger.info(f"   Genes: {', '.join(symbols)}")
        return cached

    logger.info(f"\n🔄 Running enrichment analysis on {len(symbols)} genes...")
    logger.info(f"   Genes: {', '.join(symbols)}")

    results = {}
    for library in libraries:
        logger.info(f"\n   📚 {library}...")

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
                logger.info(
                    f"      {sig_count} significant terms (adj p < 0.05) "
                    f"out of {results[library]['total_significant']} total hits"
                )
            else:
                results[library] = {
                    "library": library,
                    "terms": [],
                    "total_significant": 0,
                }
                logger.info("      No results returned")

        except ExternalAPIError as e:
            logger.info(f"      ❌ Error: {e}")
            results[library] = {
                "library": library,
                "terms": [],
                "total_significant": 0,
                "error": str(e),
            }
        except (ConnectionError, TimeoutError, OSError, ValueError) as e:
            err = classify_api_error(e, f"Enrichr {library}")
            logger.info(f"      ❌ Error: {err}")
            results[library] = {
                "library": library,
                "terms": [],
                "total_significant": 0,
                "error": str(err),
            }

    # Save to cache
    try:
        cache_set(NS_ENRICHMENT, cache_lookup_key, results, use_cache=use_cache)
        logger.info("\n💾 Cached enrichment results (namespace=%s)", NS_ENRICHMENT)
    except OSError as e:
        logger.info(f"   ⚠️  Cache write error: {e}")

    return results


def cross_reference_with_kg_pathways(
    enrichment_results: dict, kg_pathways: dict, disease_id: str = "sle"
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
                                *__import__("med_research.diseases.base", fromlist=["Disease"]).Disease(disease_id).get_pathway_keywords(),
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


def run_enrichment_analysis(
    disease_id: str = "sle",
    untargeted_only: bool = False,
    use_cache: bool = True,
) -> dict:
    """Run pathway enrichment for a disease (engine entry point)."""
    from med_research.diseases.coverage import module_coverage

    coverage = module_coverage(disease_id, "enrichment", ("genes", "pathways"))
    if not coverage.is_runnable:
        return {
            "coverage": coverage.to_dict(),
            "status": "blocked",
            "enrichment_results": {},
            "gene_list": [],
            "kg_pathway_matches": {},
        }

    logger.info("🔄 Loading knowledge graph and gene data...")
    G = load_kg_graph(disease_id)
    genes = load_kg_genes(disease_id)
    logger.info(f"   Loaded {len(genes)} genes from knowledge graph")

    logger.info("🔄 Preparing disease gene list...")
    gene_list = get_disease_gene_list(
        genes, G, untargeted_only=untargeted_only, disease_id=disease_id
    )
    logger.info(f"   Using {len(gene_list)} genes for enrichment")

    logger.info("🔄 Running enrichment analysis...")
    enrichment_results = run_enrichment(gene_list, use_cache=use_cache)

    logger.info("🔄 Cross-referencing with KG pathways...")
    kg_pathways = load_pathways(disease_id)
    kg_matches = cross_reference_with_kg_pathways(
        enrichment_results, kg_pathways, disease_id=disease_id
    )

    analyze(enrichment_results, gene_list, kg_matches)

    os.makedirs(DATA_DIR, exist_ok=True)
    output = {
        "coverage": coverage.to_dict(),
        "status": "ready",
        "gene_list": gene_list,
        "enrichment_results": enrichment_results,
        "kg_pathway_matches": {k: v for k, v in kg_matches.items()},
    }
    out_path = DATA_DIR / "enrichment_results.json"
    out_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    logger.info(f"\n💾 Results saved to {out_path}")

    return output


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
    parser.add_argument(
        "--disease", "-d", default="sle", help="Disease ID (default: sle)"
    )
    args = parser.parse_args()

    result = run_enrichment_analysis(
        disease_id=args.disease,
        untargeted_only=args.untargeted_only,
        use_cache=not args.no_cache,
    )
    if result.get("status") == "blocked":
        logger.error(
            f"❌ Enrichment blocked for {args.disease}: "
            f"{', '.join(result['coverage'].get('missing_inputs', []))}"
        )
        return result

    if args.export_html:
        from med_research.pipeline.bioinformatics.report import generate_bioinformatics_report
        from med_research.pipeline.provenance import build_provenance

        provenance = build_provenance(
            disease_id=args.disease,
            module="bioinformatics",
            sources=["enrichr"],
            cache_or_live="cache",
            scoring={"analysis": "pathway_enrichment"},
        )
        report_path = generate_bioinformatics_report(
            result["enrichment_results"],
            result["gene_list"],
            result["kg_pathway_matches"],
            None,
            None,
            disease_id=args.disease,
            provenance=provenance,
        )
        logger.info(f"\n✅ Report generated: {report_path}")

    return result["enrichment_results"]


def analyze(enrichment_results: dict, gene_list: list, kg_matches: dict):
    """Print enrichment analysis summary."""
    logger.info("\n" + "=" * 70)
    logger.info("📊 PATHWAY ENRICHMENT ANALYSIS")
    logger.info("=" * 70)

    logger.info(f"\n  Genes analyzed: {len(gene_list)}")
    logger.info(f"  Gene set libraries queried: {len(enrichment_results)}")

    for library, result in enrichment_results.items():
        lib_name = result.get("library", library)
        n_terms = len(result.get("terms", []))
        n_sig = len(
            [t for t in result.get("terms", []) if t["adj_p_value"] < 0.05]
        )
        logger.info(f"\n  📚 {lib_name}")
        logger.info(f"     {n_terms} top terms ({n_sig} significant at adj p < 0.05)")

        for i, term in enumerate(result.get("terms", [])[:8], 1):
            sig_marker = (
                "✅" if term["adj_p_value"] < 0.05 else "  "
            )
            logger.info(
                f"     {sig_marker} {i}. {term['term'][:70]}"
            )
            logger.info(
                f"         P={term['p_value']:.2e} | "
                f"adj P={term['adj_p_value']:.2e} | "
                f"OR={term['odds_ratio']:.1f} | "
                f"Genes: {', '.join(term['genes'][:5])}"
            )

    if kg_matches:
        logger.info(f"\n  🔗 Cross-reference with KG pathways ({len(kg_matches)} matches):")
        for _, matches_list in sorted(
            kg_matches.items(),
            key=lambda x: min(m["adj_p_value"] for m in x[1]),
        ):
            best = min(matches_list, key=lambda m: m["adj_p_value"])
            logger.info(
                f"     {best['kg_pathway_name'][:40]} ↔ "
                f"{best['enrichment_term'][:50]} "
                f"(P={best['adj_p_value']:.1e})"
            )


if __name__ == "__main__":
    result = main()
    if isinstance(result, dict) and result.get("status") == "blocked":
        raise SystemExit(1)
