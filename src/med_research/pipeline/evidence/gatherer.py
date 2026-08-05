"""
Web-Scale Evidence Gatherer — Multi-Source Biomedical Evidence Aggregation

Searches 5+ biomedical sources simultaneously for any query and
cross-references results across sources.

Sources:
  1. PubMed (via Europe PMC) — peer-reviewed literature
  2. Preprints (bioRxiv / medRxiv via Europe PMC) — cutting-edge findings
  3. Clinical Trials (ClinicalTrials.gov cache) — active/recruiting studies
  4. FDA Labels (DailyMed) — approved drug prescribing information
  5. Patents (via Europe PMC) — intellectual property filings

Usage:
    python evidence_gatherer/gatherer.py --query "B cell depletion lupus"
    python evidence_gatherer/gatherer.py --query "JAK inhibitor lupus" --sources pubmed,preprints,clinical_trials
    python evidence_gatherer/gatherer.py --query "CAR-T lupus" --export-html
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = Path(__file__).parent / "data"
CACHE_PATH = DATA_DIR / "evidence_cache.json"

EUROPE_PMC_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
DAILYMED_URL = "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json"

DEFAULT_SOURCES = ["pubmed", "preprints", "clinical_trials", "fda_labels", "patents"]


# ── Helpers ──────────────────────────────────────────────────────────────


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def api_get(url: str, timeout: int = 15) -> dict | None:
    """Fetch JSON from a REST API with error handling."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LupusResearchPlatform/2.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
        print(f"  ⚠️  API error ({url[:80]}...): {e}")
        return None


# ── Cache ────────────────────────────────────────────────────────────────


def _cache_key(query: str, source: str, max_results: int) -> str:
    return f"{query}|||{source}|||{max_results}"


def load_cache() -> dict:
    if CACHE_PATH.exists():
        return load_json(CACHE_PATH)
    return {}


def save_cache(cache: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    save_json(CACHE_PATH, cache)


# ── Europe PMC Search ────────────────────────────────────────────────────


def search_europe_pmc(query: str, source: str, max_results: int = 20, use_cache: bool = True) -> list:
    """Search Europe PMC for PubMed articles, preprints, or patents.

    Args:
        query: Search query string.
        source: One of 'pubmed', 'preprints', 'patents'.
        max_results: Max results to return.
        use_cache: Whether to use cached results.

    Returns:
        List of result dicts with keys: title, source, source_type, year, url, snippet, authors.
    """
    cache = load_cache()
    key = _cache_key(query, source, max_results)
    if use_cache and key in cache:
        print(f"  📦 Using cached {source} results ({len(cache[key])} items)")
        return cache[key]

    # Build query with source filter
    if source == "preprints":
        query_str = f'({query}) AND (SRC:PPR)'
    elif source == "patents":
        query_str = f'({query}) AND (SRC:PAT)'
    else:
        query_str = f'({query}) AND (SRC:MED)'

    params = urllib.parse.urlencode({
        "query": query_str,
        "resultType": "core",
        "pageSize": min(max_results, 50),
        "format": "json",
        "sort": "CITED desc",
    })
    url = f"{EUROPE_PMC_URL}?{params}"

    print(f"  🔎 Searching {source} via Europe PMC...")
    data = api_get(url)
    if not data:
        return []

    results = []
    for item in data.get("resultList", {}).get("result", [])[:max_results]:
        pub_year = item.get("pubYear", "")
        results.append({
            "title": item.get("title", "").strip(),
            "source": item.get("journalTitle", item.get("source", "Europe PMC")),
            "source_type": source,
            "year": pub_year,
            "url": f"https://europepmc.org/article/{item.get('source','MED')}/{item.get('id','')}",
            "snippet": _clean_snippet(item),
            "authors": item.get("authorString", "")[:200] if item.get("authorString") else "",
            "citation_count": item.get("citedByCount", 0),
            "id": item.get("id", ""),
        })

    cache[key] = results
    save_cache(cache)
    return results


def _clean_snippet(item: dict) -> str:
    """Extract a relevant snippet from the result."""
    snippets = []
    for field in ("abstractText", "title"):
        text = item.get(field, "")
        if text:
            snippets.append(text[:400])
    return " ".join(snippets)[:500]


# ── Clinical Trials Search ───────────────────────────────────────────────


def search_clinical_trials(query: str, max_results: int = 20) -> list:
    """Search cached clinical trial data for matching trials.

    Uses the existing clinical_trials/data/ct_results.json file.
    """
    print("  🔎 Searching clinical trials...")
    try:
        ct_data = load_json(Path("clinical_trials/data/ct_results.json"))
    except (FileNotFoundError, json.JSONDecodeError):
        print("  ⚠️  No clinical trial cache found. Run 'python main.py trials' first.")
        return []

    trials = ct_data.get("studies", [])
    query_lower = query.lower()
    results = []

    for trial in trials:
        protocol = trial.get("protocolSection", {})
        ident = protocol.get("identificationModule", {})
        status = protocol.get("statusModule", {})
        desc = protocol.get("descriptionModule", {})

        title = ident.get("briefTitle", ident.get("officialTitle", ""))
        nct_id = ident.get("nctId", "")
        conditions = protocol.get("conditionsModule", {}).get("conditions", [])
        brief = desc.get("briefSummary", "")

        # Simple relevance scoring
        text_to_match = f"{title} {' '.join(conditions)} {brief}".lower()
        relevance = sum(1 for word in query_lower.split() if word in text_to_match)

        if relevance > 0:
            results.append({
                "title": title[:200],
                "source": "ClinicalTrials.gov",
                "source_type": "clinical_trials",
                "year": status.get("startDateStruct", {}).get("date", "")[:4],
                "url": f"https://clinicaltrials.gov/study/{nct_id}",
                "snippet": brief[:400],
                "authors": "",
                "citation_count": 0,
                "id": nct_id,
                "nct_id": nct_id,
                "status": status.get("overallStatus", ""),
                "phase": protocol.get("designModule", {}).get("phases", []),
                "conditions": conditions[:5],
                "relevance": relevance,
            })

    results.sort(key=lambda x: x["relevance"], reverse=True)
    return results[:max_results]


# ── FDA Labels Search ────────────────────────────────────────────────────


def search_fda_labels(query: str, max_results: int = 20, use_cache: bool = True) -> list:
    """Search DailyMed for FDA-approved drug labels matching the query."""
    cache = load_cache()
    key = _cache_key(query, "fda_labels", max_results)
    if use_cache and key in cache:
        print(f"  📦 Using cached FDA label results ({len(cache[key])} items)")
        return cache[key]

    print("  🔎 Searching FDA labels via DailyMed...")
    params = urllib.parse.urlencode({
        "searchterms": query,
        "pagesize": min(max_results, 50),
    })
    url = f"{DAILYMED_URL}?{params}"

    data = api_get(url)
    if not data:
        return []

    results = []
    for item in data.get("data", [])[:max_results]:
        results.append({
            "title": item.get("title", "").strip()[:200],
            "source": "FDA Label (DailyMed)",
            "source_type": "fda_labels",
            "year": item.get("updated_date", "")[:4],
            "url": f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={item.get('setid','')}",
            "snippet": _extract_label_snippet(item),
            "authors": "",
            "citation_count": 0,
            "id": item.get("setid", ""),
            "drug_name": _extract_drug_name(item),
            "label_id": item.get("setid", ""),
        })

    cache[key] = results
    save_cache(cache)
    return results


def _extract_drug_name(item: dict) -> str:
    """Extract drug name from DailyMed result."""
    title = item.get("title", "")
    # Titles are like "HUMIRA (adalimumab) injection"
    if "(" in title:
        return title.split("(")[-1].split(")")[0].strip()
    return title.split(",")[0].strip()


def _extract_label_snippet(item: dict) -> str:
    """Extract a meaningful snippet from the label metadata."""
    # DailyMed SPL JSON response includes the title and setid;
    # full indications text requires fetching the SPL XML separately.
    title = item.get("title", "")
    return title[:400]


# ── Cross-Source Aggregation ─────────────────────────────────────────────


def gather_evidence(
    query: str,
    sources: list = None,
    max_per_source: int = 20,
    use_cache: bool = True,
    cross_reference: bool = True,
) -> dict:
    """Search all configured sources and aggregate results.

    Args:
        query: Search query (natural language supported).
        sources: List of source types to search (default: all).
        max_per_source: Max results per source.
        use_cache: Whether to use cached results.
        cross_reference: Whether to compute cross-source overlap stats.

    Returns:
        Dict with keys: query, total_results, results_by_source, all_results, crossref.
    """
    if sources is None:
        sources = DEFAULT_SOURCES

    start_time = time.time()
    all_results = []

    for src in sources:
        if src in ("pubmed", "preprints", "patents"):
            results = search_europe_pmc(query, src, max_per_source, use_cache)
            all_results.extend(results)
            print(f"     → {len(results)} {src} results")

        elif src == "clinical_trials":
            results = search_clinical_trials(query, max_per_source)
            all_results.extend(results)
            print(f"     → {len(results)} clinical trial results")

        elif src == "fda_labels":
            results = search_fda_labels(query, max_per_source, use_cache)
            all_results.extend(results)
            print(f"     → {len(results)} FDA label results")

    # Sort all results: mix of recency + citation weight
    def _sort_key(r):
        year_score = int(r.get("year", 0) or 0) / 2030
        cite_score = min(r.get("citation_count", 0), 100) / 100
        return year_score * 0.6 + cite_score * 0.4

    all_results.sort(key=_sort_key, reverse=True)

    elapsed = time.time() - start_time

    # Cross-reference: count overlaps between sources
    crossref = {}
    if cross_reference and len(sources) > 1:
        crossref = _compute_crossref(all_results, sources)

    output = {
        "query": query,
        "sources_searched": sources,
        "total_results": len(all_results),
        "elapsed_seconds": round(elapsed, 1),
        "results_by_source": _counts_by_source(all_results),
        "crossref": crossref,
        "all_results": all_results,
        "generated_at": datetime.now().isoformat(),
    }

    # Save results
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    save_json(DATA_DIR / "evidence_results.json", output)

    return output


def _counts_by_source(results: list) -> dict:
    counts = {}
    for r in results:
        src = r.get("source_type", "unknown")
        counts[src] = counts.get(src, 0) + 1
    return counts


def _compute_crossref(results: list, sources: list) -> dict:
    """Compute simple cross-source overlap statistics."""
    crossref = {"pairs": []}
    source_sets = {}
    for src in sources:
        source_sets[src] = {
            r["title"].lower()[:80] for r in results
            if r.get("source_type") == src
        }

    # Check for similar titles across sources (fuzzy overlap detection)
    for s1 in sources:
        for s2 in sources:
            if s1 >= s2:
                continue
            set1 = source_sets.get(s1, set())
            set2 = source_sets.get(s2, set())
            # Find titles that appear in both (exact match on first 60 chars)
            common = len(set1 & set2)
            crossref["pairs"].append({
                "source_a": s1,
                "source_b": s2,
                "overlap_count": common,
            })
    return crossref


# ── CLI ──────────────────────────────────────────────────────────────────


def print_summary(gathered: dict):
    """Print a formatted summary of gathered evidence."""
    print("\n" + "=" * 75)
    print("🌐 WEB-SCALE EVIDENCE GATHERER — Results")
    print("=" * 75)

    print(f"\n  Query: \"{gathered['query']}\"")
    print(f"  Sources searched: {', '.join(gathered['sources_searched'])}")
    print(f"  Total results: {gathered['total_results']} ({gathered['elapsed_seconds']}s)")

    print("\n  📊 Results by source:")
    for src, count in gathered["results_by_source"].items():
        icon = {"pubmed": "📄", "preprints": "🧪", "patents": "💡",
                "clinical_trials": "🏥", "fda_labels": "💊"}.get(src, "📌")
        print(f"    {icon} {src}: {count}")

    if gathered.get("crossref", {}).get("pairs"):
        print("\n  🔗 Cross-source overlaps:")
        for pair in gathered["crossref"]["pairs"]:
            if pair["overlap_count"] > 0:
                print(f"    {pair['source_a']} ↔ {pair['source_b']}: {pair['overlap_count']} overlapping")

    print("\n  📋 Top results:")
    for i, r in enumerate(gathered["all_results"][:10], 1):
        yr = r.get("year", "????")
        src = r.get("source_type", "?")
        title = r["title"][:90]
        print(f"  {i:2d}. [{yr}] [{src:15s}] {title}")


def main():
    parser = argparse.ArgumentParser(
        description="Web-Scale Evidence Gatherer — Multi-source biomedical evidence aggregation"
    )
    parser.add_argument("--query", "-q", type=str, default="B cell depletion therapy lupus",
                        help="Search query (natural language)")
    parser.add_argument("--sources", type=str, default="all",
                        help="Comma-separated sources or 'all' (pubmed,preprints,clinical_trials,fda_labels,patents)")
    parser.add_argument("--max", type=int, default=20, dest="max_per_source",
                        help="Max results per source (default: 20)")
    parser.add_argument("--no-cache", action="store_true", help="Skip cache, re-fetch from APIs")
    parser.add_argument("--top", type=int, default=15, help="Number of top results to display")
    parser.add_argument("--export-html", action="store_true", help="Generate HTML report")

    args = parser.parse_args()

    sources = DEFAULT_SOURCES if args.sources == "all" else [s.strip() for s in args.sources.split(",")]

    print("🌐 Web-Scale Evidence Gatherer")
    print(f"   Query: \"{args.query}\"")
    print(f"   Sources: {', '.join(sources)}\n")

    results = gather_evidence(
        args.query,
        sources=sources,
        max_per_source=args.max_per_source,
        use_cache=not args.no_cache,
    )

    print_summary(results)

    if args.export_html:
        from med_research.pipeline.evidence.gatherer_report import generate_html_report
        generate_html_report(results)
        print("\n✅ HTML report generated: evidence_gatherer/report.html")

    return results


if __name__ == "__main__":
    main()
