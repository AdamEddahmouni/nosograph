"""
Lupus Protein-Protein Interaction Network Analysis

Builds a PPI network for lupus-associated genes using the STRING API
(https://string-db.org/), then analyzes network topology to identify
hub proteins and potential drug targets.

The STRING API is free and requires no API key.

Usage:
    python ppi.py                      # Full analysis
    python ppi.py --confidence 0.7     # Higher confidence threshold
    python ppi.py --max-neighbors 20   # Max first neighbors to add
"""

import argparse
import json
import logging
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

import networkx as nx

from med_research.cache import NS_PPI, cache_get, cache_set, load_legacy_json
from med_research.exceptions import ExternalAPIError, classify_api_error, retry_with_backoff
from med_research.pipeline.knowledge_graph.config import load_genes as load_kg_genes
from med_research.pipeline.progress import StandardProgress, _tick, cli_progress
from med_research.pipeline.results import PpiResult

logger = logging.getLogger(__name__)

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logger.info("⚠️  requests not installed. Install with: pip install requests")

DATA_DIR = Path(__file__).parent / "data"
LEGACY_PPI_CACHE = DATA_DIR / "ppi_cache.json"
last_coverage = None
DR_DATA_DIR = Path(__file__).parent.parent / "drug_repurposing" / "data"

STRING_API = "https://string-db.org/api"
DEFAULT_SPECIES = 9606  # Homo sapiens
DEFAULT_CONFIDENCE = 0.4  # Medium confidence


def _string_http_get(path: str, params: dict, timeout: int = 30) -> Any:
    """Perform a STRING API GET request, raising on HTTP failure."""
    resp = requests.get(f"{STRING_API}/{path}", params=params, timeout=timeout)
    resp.raise_for_status()
    return resp


def load_genes(disease_id: str = "sle") -> dict:
    """Load a disease's genes from the knowledge graph."""
    data = load_kg_genes(disease_id)
    return {g["id"]: g for g in data["genes"]}


def get_gene_symbols(
    genes: dict, exclude_drug_targets: bool = True, disease_id: str = "sle"
) -> list:
    """
    Get gene symbols for STRING query, excluding drug-target-only genes.

    Returns list of (gene_id, symbol) tuples.
    """
    from med_research.diseases.base import Disease

    exclusions = set()
    if exclude_drug_targets:
        exclusions = set(Disease(disease_id).get_drug_target_exclusions())

    symbols = []
    for gene_id, _ in genes.items():
        if gene_id in exclusions:
            continue
        symbols.append((gene_id, gene_id))

    return symbols


def _fetch_ppi(symbols: list, confidence: float) -> tuple:
    """Fetch ID map and interactions from STRING API."""
    logger.info(f"\n🔄 Mapping {len(symbols)} gene symbols to STRING IDs...")
    id_map = _string_id_map(symbols)
    string_ids = list(id_map.values())
    logger.info(f"   Mapped {len(string_ids)}/{len(symbols)} symbols to STRING IDs")

    if not string_ids:
        logger.info("   ❌ No STRING IDs found. Check gene symbols.")
        return {}, []

    logger.info(f"\n🔄 Fetching PPI network (confidence ≥ {confidence})...")
    interactions = _string_network(string_ids, confidence)
    logger.info(f"   Retrieved {len(interactions)} interactions")

    return id_map, interactions


def _string_id_map(symbols: list) -> dict:
    """
    Map gene symbols to STRING protein IDs.

    STRING API endpoint: /api/tsv/get_string_ids
    """
    params = {
        "identifiers": "\r".join(symbols),
        "species": DEFAULT_SPECIES,
        "limit": 1,
        "echo_query": 1,
    }

    try:
        resp = retry_with_backoff(
            lambda: _string_http_get(
                "tsv/get_string_ids",
                params,
                timeout=30,
            ),
            source="STRING ID mapping",
        )

        mapping = {}
        for line in resp.text.strip().split("\n")[1:]:  # Skip header
            parts = line.split("\t")
            if len(parts) >= 3:
                query = parts[0].strip()
                string_id = parts[2].strip()
                if string_id:
                    mapping[query] = string_id

        return mapping
    except ExternalAPIError as e:
        logger.info(f"   ⚠️  {e}")
        return {}
    except requests.exceptions.RequestException as e:
        err = classify_api_error(e, "STRING ID mapping")
        logger.info(f"   ⚠️  {err}")
        return {}


def _string_network(string_ids: list, confidence: float = 0.4) -> list:
    """
    Fetch PPI network from STRING for given protein IDs.

    Returns list of interaction dicts: {stringId_A, stringId_B, score, ...}
    """
    params = {
        "identifiers": "%0d".join(string_ids),
        "species": DEFAULT_SPECIES,
        "required_score": int(confidence * 1000),
        "network_type": "functional",
    }

    interactions = []

    try:
        resp = retry_with_backoff(
            lambda: _string_http_get(
                "tsv/network",
                params,
                timeout=60,
            ),
            source="STRING network fetch",
        )

        for line in resp.text.strip().split("\n")[1:]:  # Skip header
            parts = line.split("\t")
            if len(parts) >= 6:
                interactions.append(
                    {
                        "stringId_A": parts[0].strip(),
                        "stringId_B": parts[1].strip(),
                        "preferredName_A": parts[2].strip(),
                        "preferredName_B": parts[3].strip(),
                        "score": float(parts[5].strip()) if len(parts) > 5 else 0.0,
                    }
                )

    except ExternalAPIError as e:
        logger.info(f"   ⚠️  {e}")
    except requests.exceptions.RequestException as e:
        err = classify_api_error(e, "STRING network fetch")
        logger.info(f"   ⚠️  {err}")

    return interactions


def build_ppi_network(
    gene_symbols: list,
    confidence: float = DEFAULT_CONFIDENCE,
    expand_neighbors: int = 0,
    use_cache: bool = True,
) -> nx.Graph:
    """
    Build a PPI network from STRING for the given gene symbols.

    Args:
        gene_symbols: List of (gene_id, symbol) tuples
        confidence: STRING combined score threshold (0-1)
        expand_neighbors: Max number of first-neighbor proteins to add
                          (0 = only query proteins)
        use_cache: Load from cache if available

    Returns:
        NetworkX graph with node attributes: symbol, gene_id, is_seed
    """
    if not REQUESTS_AVAILABLE:
        logger.info("❌ requests required. Install: pip install requests")
        return nx.Graph()

    symbols = [s for _, s in gene_symbols]
    symbol_to_gene_id = {s: gid for gid, s in gene_symbols}
    cache_key = ",".join(sorted(symbols))
    cache_lookup_key = f"{cache_key}|||{confidence}"

    # Check cache
    freshly_fetched = False
    cached = cache_get(NS_PPI, cache_lookup_key, use_cache=use_cache)
    if cached is None and use_cache:
        legacy = load_legacy_json(LEGACY_PPI_CACHE)
        if (
            legacy
            and legacy.get("cache_key") == cache_key
            and legacy.get("confidence") == confidence
        ):
            cached = legacy
            cache_set(NS_PPI, cache_lookup_key, cached, use_cache=True)

    if cached is not None:
        try:
            if cached.get("cache_key") == cache_key and cached.get("confidence") == confidence:
                logger.info("📦 Loading PPI network from cache...")
                id_map = cached["id_map"]
                interactions = cached["interactions"]
                if not id_map:
                    logger.info("   ❌ Cached PPI network is empty. Re-fetching...")
                    id_map, interactions = _fetch_ppi(symbols, confidence)
                    freshly_fetched = True
            else:
                logger.info("   ⚠️  Cache key mismatch, re-fetching PPI network...")
                id_map, interactions = _fetch_ppi(symbols, confidence)
                freshly_fetched = True
        except (KeyError, TypeError):
            logger.info("   ⚠️  Corrupt cache, re-fetching PPI network...")
            id_map, interactions = _fetch_ppi(symbols, confidence)
            freshly_fetched = True
    else:
        id_map, interactions = _fetch_ppi(symbols, confidence)
        freshly_fetched = True

    # Save fresh data to cache (only when we fetched new data)
    if use_cache and freshly_fetched:
        try:
            cache_set(
                NS_PPI,
                cache_lookup_key,
                {
                    "cache_key": cache_key,
                    "confidence": confidence,
                    "id_map": id_map,
                    "interactions": interactions,
                },
                use_cache=True,
            )
            logger.info("💾 Cached PPI network (namespace=%s)", NS_PPI)
        except OSError as e:
            logger.info(f"   ⚠️  Cache write error: {e}")

    if not id_map:
        logger.info("   ❌ No STRING IDs found. Check gene symbols.")
        return nx.Graph()

    # Build graph
    G = nx.Graph()

    # Add seed nodes
    seed_string_ids = set()
    for symbol, string_id in id_map.items():
        gene_id = symbol_to_gene_id.get(symbol, symbol)
        G.add_node(
            string_id,
            symbol=symbol,
            gene_id=gene_id,
            is_seed=True,
            is_lupus_gene=True,
        )
        seed_string_ids.add(string_id)

    # Add edges
    seen_nodes = set(seed_string_ids)
    for inter in interactions:
        a = inter["stringId_A"]
        b = inter["stringId_B"]

        # Add non-seed nodes
        for node_id in [a, b]:
            if node_id not in seen_nodes:
                name = inter.get(f"preferredName_{'A' if node_id == a else 'B'}", node_id)
                G.add_node(
                    node_id,
                    symbol=name,
                    gene_id=None,
                    is_seed=False,
                    is_lupus_gene=False,
                )
                seen_nodes.add(node_id)

        G.add_edge(
            a,
            b,
            score=inter["score"],
            weight=inter["score"],
        )

    logger.info(
        f"   Network: {G.number_of_nodes()} nodes, "
        f"{G.number_of_edges()} edges "
        f"({len(seed_string_ids)} seed genes)"
    )

    return G


def compute_hub_scores(G: nx.Graph) -> list:
    """
    Compute hub scores for all nodes using multiple centrality metrics.

    Returns list of dicts sorted by composite hub score (descending).
    """
    if G.number_of_nodes() == 0:
        return []

    logger.info("\n🔄 Computing hub scores...")

    # Degree centrality
    degree = nx.degree_centrality(G)

    # Betweenness centrality
    betweenness = nx.betweenness_centrality(G, weight="weight")

    # Composite hub score (normalized average)
    hub_scores = []
    for node in G.nodes():
        d = degree.get(node, 0)
        b = betweenness.get(node, 0)
        composite = (d + b) / 2.0
        is_seed = G.nodes[node].get("is_seed", False)
        hub_scores.append(
            {
                "node_id": node,
                "symbol": G.nodes[node].get("symbol", node),
                "gene_id": G.nodes[node].get("gene_id"),
                "is_seed": is_seed,
                "is_lupus_gene": G.nodes[node].get("is_lupus_gene", False),
                "degree": G.degree(node),
                "degree_centrality": round(d, 4),
                "betweenness_centrality": round(b, 4),
                "hub_score": round(composite, 4),
            }
        )

    hub_scores.sort(key=lambda x: x["hub_score"], reverse=True)
    return hub_scores


def cross_reference_with_candidates(
    hub_scores: list,
    ppi_graph: nx.Graph,
    genes: dict,
    candidates: list,
) -> dict:
    """
    Cross-reference PPI hub proteins with drug repurposing candidates.

    Identifies:
      1. Hub proteins that ARE drug repurposing targets (direct validation)
      2. Hub proteins NOT yet targeted (new opportunities)
      3. Drugs targeting hub proteins
    """
    # Build lookup: gene_id → repurposing candidates
    gene_candidates = defaultdict(list)
    for c in candidates:
        gene_candidates[c["gene_id"]].append(c)

    # Hub proteins that are lupus genes
    lupus_hubs = [h for h in hub_scores if h["is_lupus_gene"]]
    non_lupus_hubs = [h for h in hub_scores if not h["is_lupus_gene"]]

    # Match hubs to candidates
    hub_candidate_matches = []
    hub_untargeted = []

    for hub in lupus_hubs:
        gene_id = hub.get("gene_id")
        if gene_id and gene_id in gene_candidates:
            hub_candidate_matches.append(
                {
                    **hub,
                    "candidates": gene_candidates[gene_id],
                    "n_candidates": len(gene_candidates[gene_id]),
                }
            )
        elif gene_id:
            hub_untargeted.append(hub)

    return {
        "lupus_hubs": lupus_hubs,
        "non_lupus_hubs": non_lupus_hubs[:15],
        "hub_candidate_matches": sorted(
            hub_candidate_matches,
            key=lambda x: x["hub_score"],
            reverse=True,
        ),
        "hub_untargeted": sorted(hub_untargeted, key=lambda x: x["hub_score"], reverse=True),
        "top_hubs_overall": hub_scores[:15],
    }


def analyze(hub_scores: list, crossref: dict, G: nx.Graph) -> None:
    """Print PPI network analysis summary."""
    logger.info("\n" + "=" * 70)
    logger.info("🔗 PROTEIN-PROTEIN INTERACTION NETWORK ANALYSIS")
    logger.info("=" * 70)

    logger.info(
        f"\n  Network size: {G.number_of_nodes()} proteins, {G.number_of_edges()} interactions"
    )

    # Top hubs
    logger.info("\n  🏆 Top 10 Hub Proteins:")
    for i, h in enumerate(hub_scores[:10], 1):
        marker = "🧬" if h["is_lupus_gene"] else "🔹"
        logger.info(
            f"     {i}. {marker} {h['symbol']:<18} "
            f"Hub: {h['hub_score']:.3f} | "
            f"Deg: {h['degree']} | "
            f"Betw: {h['betweenness_centrality']:.3f}"
        )

    # Hub candidates
    matches = crossref.get("hub_candidate_matches", [])
    if matches:
        logger.info("\n  🎯 Hub proteins with repurposing candidates:")
        for m in matches[:8]:
            top_cand = m["candidates"][0]
            logger.info(
                f"     • {m['symbol']} (hub={m['hub_score']:.3f}) → "
                f"{m['n_candidates']} candidate(s) "
                f"(best: {top_cand['drug_name'][:50]}, "
                f"score={top_cand.get('composite_score', '?')})"
            )

    # Untargeted hubs
    untargeted = crossref.get("hub_untargeted", [])
    if untargeted:
        logger.info("\n  💡 Hub proteins with NO repurposing candidates (new opportunities):")
        for u in untargeted[:8]:
            logger.info(f"     • {u['symbol']} (hub={u['hub_score']:.3f}, deg={u['degree']})")

    # Non-lupus hubs
    non_lupus = crossref.get("non_lupus_hubs", [])[:8]
    if non_lupus:
        logger.info("\n  🔬 Top non-lupus hub proteins (potential indirect targets):")
        for n in non_lupus:
            logger.info(f"     • {n['symbol']} (hub={n['hub_score']:.3f}, deg={n['degree']})")


def run_ppi_analysis(
    disease_id: str = "sle",
    confidence: float = DEFAULT_CONFIDENCE,
    expand_neighbors: int = 0,
    use_cache: bool = True,
    progress_callback: StandardProgress | None = None,
) -> PpiResult:
    """Build PPI network and hub scores for a disease (engine entry point)."""
    from med_research.diseases.coverage import module_coverage

    coverage = module_coverage(disease_id, "ppi", ("genes",))
    if not coverage.is_runnable:
        return {
            "coverage": coverage.to_dict(),
            "status": "blocked",
            "hub_scores": [],
            "crossref": {},
            "graph": {"nodes": [], "edges": []},
            "confidence": confidence,
        }

    logger.info("Loading gene and candidate data...")
    genes = load_genes(disease_id)
    gene_symbols = get_gene_symbols(genes, disease_id=disease_id)
    logger.info(f"   Loaded {len(gene_symbols)} disease gene symbols")

    logger.info("🔄 Loading repurposing candidates...")
    candidates_data = json.loads((DR_DATA_DIR / "candidates.json").read_text(encoding="utf-8"))
    candidates = candidates_data["repurposing_candidates"]
    logger.info(f"   Loaded {len(candidates)} candidates")

    logger.info("🔄 Building PPI network...")
    _tick(progress_callback, "building PPI network", 1, 4)
    G = build_ppi_network(
        gene_symbols,
        confidence=confidence,
        expand_neighbors=expand_neighbors,
        use_cache=use_cache,
    )

    if G.number_of_nodes() == 0:
        logger.error("❌ Empty PPI network. Cannot proceed.")
        return {
            "coverage": coverage.to_dict(),
            "status": "limited_coverage",
            "hub_scores": [],
            "crossref": {},
            "graph": {"nodes": [], "edges": []},
            "confidence": confidence,
        }

    logger.info("🔄 Computing hub scores...")
    _tick(progress_callback, "computing hub scores", 2, 4)
    hub_scores = compute_hub_scores(G)

    logger.info("🔄 Cross-referencing with repurposing candidates...")
    _tick(progress_callback, "cross-referencing candidates", 3, 4)
    crossref = cross_reference_with_candidates(hub_scores, G, genes, candidates)

    analyze(hub_scores, crossref, G)
    _tick(progress_callback, "finalizing PPI results", 4, 4)

    graph_data = {
        "nodes": [
            {
                "id": n,
                "symbol": G.nodes[n].get("symbol", n),
                "gene_id": G.nodes[n].get("gene_id"),
                "is_seed": G.nodes[n].get("is_seed", False),
                "is_lupus_gene": G.nodes[n].get("is_lupus_gene", False),
            }
            for n in G.nodes()
        ],
        "edges": [
            {"source": u, "target": v, "score": d["score"]} for u, v, d in G.edges(data=True)
        ],
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    output: PpiResult = {
        "coverage": coverage.to_dict(),
        "status": "ready",
        "hub_scores": hub_scores,
        "crossref": {
            "hub_candidate_matches": crossref["hub_candidate_matches"],
            "hub_untargeted": crossref["hub_untargeted"],
            "top_hubs_overall": crossref["top_hubs_overall"],
        },
        "graph": graph_data,
        "confidence": confidence,
    }
    out_path = DATA_DIR / "ppi_results.json"
    out_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    logger.info(f"\n💾 Results saved to {out_path}")

    return output


def main():
    parser = argparse.ArgumentParser(description="Lupus PPI Network Analysis via STRING API")
    parser.add_argument(
        "--confidence",
        type=float,
        default=DEFAULT_CONFIDENCE,
        help=f"STRING confidence threshold (default: {DEFAULT_CONFIDENCE})",
    )
    parser.add_argument(
        "--max-neighbors",
        type=int,
        default=0,
        help="Max first-neighbor proteins to add (default: 0)",
    )
    parser.add_argument("--export-html", action="store_true", help="Generate HTML report")
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Skip cache, re-fetch PPI network from STRING",
    )
    parser.add_argument("--disease", "-d", default="sle", help="Disease ID (default: sle)")
    args = parser.parse_args()

    result = run_ppi_analysis(
        disease_id=args.disease,
        confidence=args.confidence,
        expand_neighbors=args.max_neighbors,
        use_cache=not args.no_cache,
        progress_callback=cli_progress,
    )
    if result.get("status") == "blocked":
        logger.error(
            "PPI analysis blocked for %s: %s",
            args.disease,
            ", ".join(result["coverage"].get("missing_inputs", [])),
        )
        return result

    if args.export_html and result.get("hub_scores"):
        from med_research.pipeline.bioinformatics.report import generate_bioinformatics_report
        from med_research.pipeline.provenance import build_provenance

        provenance = build_provenance(
            disease_id=args.disease,
            module="bioinformatics",
            sources=["string"],
            cache_or_live="cache",
            scoring={"analysis": "ppi_hub"},
        )
        report_path = generate_bioinformatics_report(
            None,
            None,
            None,
            result["hub_scores"],
            result["crossref"],
            result["graph"],
            disease_id=args.disease,
            provenance=provenance,
        )
        logger.info(f"\n✅ Report generated: {report_path}")

    return result.get("hub_scores")


if __name__ == "__main__":
    import sys

    from med_research.cli import main as cli_main

    sys.exit(cli_main() or 0)
