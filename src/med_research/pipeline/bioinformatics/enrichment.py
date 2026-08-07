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

from med_research.pipeline.knowledge_graph.config import load_genes, load_pathways

logger = logging.getLogger(__name__)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = Path(__file__).parent / "data"
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

    The function name is retained for compatibility with existing callers;
    records and exclusions are scoped to ``disease_id``.

    Args:
        genes: Gene dictionary indexed by gene ID.
        G: Knowledge graph (optional, for targeted gene detection).
        untargeted_only: If True, only return genes not targeted by any drug.
    """
    # Drug target genes that are not lupus risk genes
    from med_research.diseases.base import Disease

    drug_target_exclusions = Disease(disease_id).get_drug_target_exclusions()

    lupus_genes = []
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

        lupus_genes.append(
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

    return lupus_genes


def get_disease_gene_list(
    genes: dict, G: nx.MultiDiGraph = None, untargeted_only: bool = False,
    disease_id: str = "sle",
) -> list:
    """Return the active disease's analyzable gene list."""
    return get_lupus_gene_list(genes, G, untargeted_only, disease_id)


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

    # Check cache
    cache_path = DATA_DIR / "enrichment_cache.json"
    if use_cache and cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if (
                cached.get("cache_key") == cache_key
                and cached.get("libraries") == libraries
                and cached.get("top_n") == top_n
            ):
                logger.info("📦 Loading enrichment results from cache...")
                logger.info(f"   Genes: {', '.join(symbols)}")
                return cached["results"]
            else:
                logger.info("   ⚠️  Cache key mismatch, re-running enrichment...")
        except (json.JSONDecodeError, KeyError):
            logger.info("   ⚠️  Corrupt cache, re-running enrichment...")

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

        except Exception as e:
            logger.info(f"      ❌ Error: {e}")
            results[library] = {
                "library": library,
                "terms": [],
                "total_significant": 0,
                "error": str(e),
            }

    # Save to cache
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        cache_path.write_text(
            json.dumps(
                {
                    "cache_key": cache_key,
                    "libraries": libraries,
                    "top_n": top_n,
                    "results": results,
                },
                indent=2,
                ensure_ascii=False,
                default=str,
            ),
            encoding="utf-8",
        )
        logger.info(f"\n💾 Cached enrichment results to {cache_path}")
    except Exception as e:
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

    from med_research.diseases.coverage import module_coverage
    coverage = module_coverage(args.disease, "enrichment", ("genes", "pathways"))
    if not coverage.is_runnable:
        logger.error(f"❌ Enrichment blocked for {args.disease}: {', '.join(coverage.missing_inputs)}")
        return {"coverage": coverage.to_dict(), "status": "blocked", "libraries": []}

    logger.info("🔄 Loading knowledge graph and gene data...")
    G = load_kg_graph(args.disease)
    genes = load_kg_genes(args.disease)
    logger.info(f"   Loaded {len(genes)} genes from knowledge graph")

    logger.info("🔄 Preparing disease gene list...")
    gene_list = get_disease_gene_list(
        genes, G, untargeted_only=args.untargeted_only, disease_id=args.disease
    )
    logger.info(f"   Using {len(gene_list)} genes for enrichment")
    for g in gene_list:
        logger.info(f"     • {g['symbol']} ({g['gene_id']}) — {g['category']}")

    logger.info("🔄 Running enrichment analysis...")
    enrichment_results = run_enrichment(
        gene_list, use_cache=not args.no_cache
    )

    logger.info("🔄 Cross-referencing with KG pathways...")
    kg_pathways = load_pathways(args.disease)
    kg_matches = cross_reference_with_kg_pathways(
        enrichment_results, kg_pathways, disease_id=args.disease
    )

    analyze(enrichment_results, gene_list, kg_matches)

    # Save results
    os.makedirs(DATA_DIR, exist_ok=True)
    output = {
        "coverage": coverage.to_dict(),
        "status": "ready",
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
    logger.info(f"\n💾 Results saved to {out_path}")

    if args.export_html:
        from med_research.pipeline.bioinformatics.report import generate_bioinformatics_report

        report_path = generate_bioinformatics_report(
            enrichment_results,
            gene_list,
            kg_matches,
            None,
            None,
            disease_id=args.disease,
        )
        logger.info(f"\n✅ Report generated: {report_path}")

    return enrichment_results


if __name__ == "__main__":
    result = main()
    if isinstance(result, dict) and result.get("status") == "blocked":
        raise SystemExit(1)
