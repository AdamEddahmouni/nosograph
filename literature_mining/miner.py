"""
Lupus Literature Miner — PubMed Search & Entity Extraction

Queries PubMed for SLE/lupus-related articles using BioPython Entrez,
extracts abstracts, and identifies named entities (genes, drugs, pathways)
using dictionary-based matching against the Lupus Knowledge Graph.

Usage:
    python miner.py                      # Full pipeline with default queries
    python miner.py --max 50             # Limit to 50 articles
    python miner.py --query "BTK lupus"  # Custom PubMed query
    python miner.py --export-html         # Generate HTML report
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from Bio import Entrez, Medline

    BIOPYTHON_AVAILABLE = True
except ImportError:
    BIOPYTHON_AVAILABLE = False
    print(
        "⚠️  BioPython not installed. Install with: pip install biopython"
    )

from literature_mining.crossref import (
    cross_reference_articles,
    load_kg_entities,
    load_repurposing_candidates,
)
from literature_mining.content_extractor import ContentExtractor

DATA_DIR = Path(__file__).parent / "data"
DEFAULT_EMAIL = "lupus-research@example.com"

# ── PubMed queries for SLE/lupus ──────────────────────────────────────────

DEFAULT_QUERIES = [
    # Broad SLE queries
    '("systemic lupus erythematosus"[MeSH Terms] OR "lupus"[Title/Abstract]) AND ("drug repurposing" OR "drug repositioning" OR "novel therapeutic" OR "new treatment") AND ("2019"[Date - Publication] : "2026"[Date - Publication])',
    # Gene-targeted queries
    '(lupus OR SLE) AND (BTK OR "Bruton tyrosine kinase" OR "tyrosine kinase 2" OR TYK2) AND ("2019"[Date - Publication] : "2026"[Date - Publication])',
    # Pathway-targeted queries
    '(lupus OR SLE) AND ("JAK inhibitor" OR "JAK-STAT" OR "type I interferon" OR "B cell depletion") AND ("therapy" OR "treatment" OR "trial") AND ("2021"[Date - Publication] : "2026"[Date - Publication])',
    # Clinical trial literature
    '(lupus OR SLE) AND ("clinical trial"[Publication Type] OR "randomized controlled trial"[Publication Type]) AND ("biologic" OR "small molecule" OR "targeted therapy") AND ("2021"[Date - Publication] : "2026"[Date - Publication])',
    # Repurposing-specific
    '(lupus OR SLE) AND ("repurposing" OR "repositioning" OR "off-label") AND ("FDA approved" OR "approved drug") AND ("2019"[Date - Publication] : "2026"[Date - Publication])',
]


def generate_candidate_queries(candidates: list) -> list:
    """
    Generate targeted PubMed queries for each repurposing candidate.

    Extracts drug generic + brand names from candidate drug names
    and creates queries like: (lupus OR SLE) AND ("fenebrutinib" OR "GDC-0853")

    Returns a list of query strings, one per candidate.
    """
    queries = []
    for c in candidates:
        drug_name = c["drug_name"]

        # Extract generic name (before parens) and brand name (in parens)
        parts = drug_name.split("(")
        generic = parts[0].strip().rstrip()
        brand = ""
        if len(parts) > 1:
            brand = parts[1].split(")")[0].strip()

        # Build drug search terms
        drug_terms = []
        if generic:
            drug_terms.append(f'"{generic}"')
        if brand and brand != generic:
            drug_terms.append(f'"{brand}"')

        # Skip if we can't extract a meaningful drug name
        if not drug_terms:
            continue

        drug_search = " OR ".join(drug_terms)
        query = f'(lupus OR SLE) AND ({drug_search})'
        queries.append((c["id"], query, c["drug_name"]))

    return queries


def search_pubmed(
    query: str, max_results: int = 50, email: str = DEFAULT_EMAIL
) -> list:
    """
    Search PubMed and return list of articles with abstracts.

    Handles rate limiting (3 req/sec without API key) automatically.
    """
    if not BIOPYTHON_AVAILABLE:
        print("❌ BioPython required. Install: pip install biopython")
        return []

    Entrez.email = email

    try:
        # Step 1: Search for IDs
        handle = Entrez.esearch(
            db="pubmed", term=query, retmax=max_results, sort="relevance"
        )
        record = Entrez.read(handle)
        handle.close()
        id_list = record["IdList"]

        if not id_list:
            return []

        print(f"   Found {record['Count']} total, retrieving {len(id_list)}...")

        # Rate limiting
        time.sleep(0.4)

        # Step 2: Fetch article details
        handle = Entrez.efetch(
            db="pubmed", id=id_list, rettype="medline", retmode="text"
        )
        records = list(Medline.parse(handle))
        handle.close()

        articles = []
        for rec in records:
            abstract = rec.get("AB", "")
            if abstract:  # Only keep articles with abstracts
                articles.append(
                    {
                        "pmid": rec.get("PMID", ""),
                        "title": rec.get("TI", ""),
                        "abstract": abstract,
                        "authors": rec.get("AU", [])[:5],
                        "journal": rec.get("JT", ""),
                        "year": rec.get("DP", "")[:4] if rec.get("DP") else "",
                        "publication_types": rec.get("PT", []),
                        "mesh_terms": rec.get("MH", []),
                    }
                )

        return articles

    except Exception as e:
        print(f"   ❌ PubMed query error: {e}")
        return []


def mine_literature(
    queries: list = None,
    max_per_query: int = 30,
    email: str = DEFAULT_EMAIL,
    use_cache: bool = True,
    targeted_candidates: bool = False,
    extract_content: bool = False,
) -> tuple:
    """
    Run the full literature mining pipeline.

    Args:
        queries: List of PubMed query strings (or None for defaults)
        max_per_query: Max articles to fetch per query
        email: NCBI Entrez email (required)
        use_cache: Load from cache if available
        targeted_candidates: Also run per-candidate targeted queries
        extract_content: Pre-filter abstracts to KG-relevant sentences

    Returns:
        (crossref_results, entities, candidates, extraction_stats)
    """
    if queries is None:
        queries = list(DEFAULT_QUERIES)

    # Load KG entities and candidates
    print("🔄 Loading knowledge graph entities...")
    entities = load_kg_entities()
    print(
        f"   Loaded {len(entities['genes'])} genes, {len(entities['drugs'])} drugs, "
        f"{len(entities['pathways'])} pathways"
    )

    print("🔄 Loading repurposing candidates...")
    candidates = load_repurposing_candidates()
    print(f"   Loaded {len(candidates)} candidates")

    # Generate per-candidate queries if requested
    candidate_queries = []
    if targeted_candidates:
        candidate_queries = generate_candidate_queries(candidates)
        print(f"   Generated {len(candidate_queries)} per-candidate queries")

    # Check cache (skip if using targeted queries, since they're per-drug)
    cache_path = DATA_DIR / "pubmed_cache.json"
    if use_cache and cache_path.exists() and not targeted_candidates:
        print("📦 Loading from PubMed cache...")
        all_articles = json.loads(cache_path.read_text(encoding="utf-8"))
        print(f"   Loaded {len(all_articles)} cached articles")
    else:
        # Search PubMed
        all_articles = []
        seen_pmids = set()

        # ── Broad queries ────────────────────────────────────────────
        for i, query in enumerate(queries, 1):
            print(f"\n🔍 Broad query {i}/{len(queries)}: {query[:100]}...")
            articles = search_pubmed(query, max_results=max_per_query, email=email)

            new_count = 0
            for article in articles:
                if article["pmid"] not in seen_pmids:
                    seen_pmids.add(article["pmid"])
                    all_articles.append(article)
                    new_count += 1

            print(f"   ✅ {new_count} new unique articles")
            time.sleep(0.5)

        # ── Per-candidate targeted queries ───────────────────────────
        if candidate_queries:
            print(f"\n🎯 Running {len(candidate_queries)} per-candidate targeted queries...")
            matches_found = 0
            for i, (cid, query, drug_label) in enumerate(candidate_queries, 1):
                articles = search_pubmed(query, max_results=3, email=email)

                new_count = 0
                for article in articles:
                    if article["pmid"] not in seen_pmids:
                        seen_pmids.add(article["pmid"])
                        all_articles.append(article)
                        new_count += 1

                if new_count > 0:
                    matches_found += 1
                    print(f"      ✅ {drug_label[:55]} → {new_count} new articles")

                if i % 15 == 0 or i == len(candidate_queries):
                    print(
                        f"   [{i}/{len(candidate_queries)}] "
                        f"{matches_found} candidates with new articles so far"
                    )

                # Rate limiting — 3 req/sec max without API key
                time.sleep(0.4)

            print(f"   ✅ {matches_found}/{len(candidate_queries)} candidates returned articles")

        # Save to cache
        os.makedirs(DATA_DIR, exist_ok=True)
        cache_path.write_text(
            json.dumps(all_articles, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"\n💾 Cached {len(all_articles)} articles to {cache_path}")

    # Cross-reference
    print("\n🔄 Cross-referencing against knowledge graph...")
    results = cross_reference_articles(all_articles, entities, candidates)

    # ── Content extraction stats ──────────────────────────────────────
    extraction_stats = None
    if extract_content:
        print("\n✂️  Content extraction: filtering abstracts to KG-relevant sentences...")
        extractor = ContentExtractor()
        extractor.known_terms = extractor.build_terms_from_entities(entities)
        _, extraction_stats = extractor.filter_articles(all_articles)

        # Also filter the articles used for cross-referencing
        all_articles_filtered = []
        for article in all_articles:
            fa = dict(article)
            fa["abstract"] = extractor.filter_abstract(fa.get("abstract", ""))
            all_articles_filtered.append(fa)

        print("🔄 Re-cross-referencing with filtered abstracts...")
        results = cross_reference_articles(all_articles_filtered, entities, candidates)
        results["extraction_stats"] = extraction_stats

    return results, entities, candidates, extraction_stats


def print_summary(results: dict, candidates: list, entities: dict):
    """Print a summary of literature mining results."""
    stats = results["stats"]
    candidate_support = results["candidate_support"]
    gene_coverage = results["gene_coverage"]

    print("\n" + "=" * 70)
    print("📚 LITERATURE MINING RESULTS")
    print("=" * 70)

    print(f"\n  Articles analyzed:           {stats['total_articles']}")
    print(f"  Articles with KG matches:    {stats['articles_with_matches']}")
    print(f"  Unique genes found:          {stats['genes_found']}")
    print(f"  Unique drugs found:          {stats['drugs_found']}")
    print(f"  spaCy biomedical NER:        {stats.get('spacy_ner', 'not available')}")
    if stats.get('novel_entities_found', 0) > 0:
        print(f"  Novel entities (spaCy):      {stats['novel_entities_found']}")
    print(
        f"  Repurposing candidates with\n"
        f"  literature support:          {stats['candidates_supported']}/{len(candidates)}"
    )

    # Build gene name lookup from entities
    gene_names = {gid: info.get("name", gid) for gid, info in entities["genes"].items()}

    # Candidates with literature support
    if candidate_support:
        print("\n  📋 Candidates with literature support:")
        for cid, articles in sorted(
            candidate_support.items(), key=lambda x: len(x[1]), reverse=True
        )[:15]:
            cand = next((c for c in candidates if c["id"] == cid), None)
            if cand:
                gene = gene_names.get(cand.get("gene_id", ""), cand.get("gene_id", "?"))
                drug = cand["drug_name"][:50]
                print(
                    f"    • {drug} → {gene} "
                    f"({len(articles)} article{'s' if len(articles) > 1 else ''})"
                )

    # Gene coverage
    if gene_coverage:
        print("\n  🧬 Gene literature coverage:")
        for gid, info in sorted(
            gene_coverage.items(), key=lambda x: x[1]["articles"], reverse=True
        ):
            gene_info = entities_hack.get(gid, {"name": gid})
            bar = "█" * min(info["articles"], 10)
            print(f"    {gene_info['name'][:40]:<42} {bar} {info['articles']}")

    # Top articles
    top_articles = [
        a for a in results["article_matches"] if a["relevance_score"] > 0
    ][:5]
    if top_articles:
        print("\n  📄 Top articles by relevance:")
        for i, a in enumerate(top_articles, 1):
            print(
                f"    {i}. [{a['year']}] {a['title'][:90]}..."
            )
            print(
                f"       Score: {a['relevance_score']} | "
                f"Genes: {a['kg_matches']['gene_count']} | "
                f"Drugs: {a['kg_matches']['drug_count']}"
            )


def main():
    parser = argparse.ArgumentParser(
        description="Lupus Literature Mining Engine — PubMed search & entity extraction"
    )
    parser.add_argument(
        "--max", type=int, default=30, help="Max articles per query (default: 30)"
    )
    parser.add_argument(
        "--query", type=str, help="Custom PubMed query (overrides defaults)"
    )
    parser.add_argument(
        "--no-cache", action="store_true", help="Skip cache, re-fetch from PubMed"
    )
    parser.add_argument(
        "--email", type=str, default=DEFAULT_EMAIL, help="Email for NCBI Entrez"
    )
    parser.add_argument(
        "--export-html", action="store_true", help="Export HTML report"
    )
    parser.add_argument(
        "--targeted", action="store_true",
        help="Also run per-candidate targeted PubMed queries (39 extra queries)"
    )
    parser.add_argument(
        "--extract", action="store_true",
        help="Pre-filter abstracts to only KG-relevant sentences (reduces NER tokens ~60%%)"
    )
    parser.add_argument(
        "--install-scispacy", action="store_true",
        help="Install scispacy biomedical NER model for enhanced entity extraction"
    )
    args = parser.parse_args()

    if args.install_scispacy:
        import subprocess
        print("Installing scispacy biomedical NER models...")
        print("Run: pip install spacy scispacy")
        print("Then: pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/"
              "releases/v0.5.4/en_ner_bc5cdr_md-0.5.4.tar.gz")
        sys.exit(0)

    queries = [args.query] if args.query else None

    results, entities, candidates, extraction_stats = mine_literature(
        queries=queries,
        max_per_query=args.max,
        email=args.email,
        use_cache=not args.no_cache,
        targeted_candidates=args.targeted,
        extract_content=args.extract,
    )

    # Store entities globally for print_summary access
    global entities_hack
    entities_hack = {
        gid: entities["genes"].get(gid, {"name": gid})
        for gid in results.get("gene_coverage", {})
    }

    print_summary(results, candidates, entities)

    if args.export_html:
        from literature_mining.report import generate_literature_report
        report_path = generate_literature_report(results, entities, candidates)
        print(f"\n✅ Literature report generated: {report_path}")

    return results


if __name__ == "__main__":
    results = main()
