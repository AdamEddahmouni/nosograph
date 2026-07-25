"""
LLM Evidence Extractor — Structured Data Extraction from Biomedical Abstracts

Uses LLMs (OpenAI-compatible API) to extract structured information from
evidence gathered by the Phase 17 Evidence Gatherer:

  - Evidence level (meta-analysis, RCT, observational, case report, preclinical, review)
  - Model system (human, murine, in vitro, in silico, ex vivo, mixed)
  - Key findings (1-3 sentence summary)
  - Drug/compound mentions
  - Disease/condition
  - Study design (double-blind, open-label, retrospective, etc.)
  - Sample size (if available)
  - P-value or effect size
  - Confidence score (0-100)

Supports:
  - OpenAI API (GPT-4, GPT-3.5, GPT-4o-mini)
  - Any OpenAI-compatible endpoint (Ollama, vLLM, LM Studio, TogetherAI, etc.)

Usage:
    python llm_extractor/extractor.py --query "B cell depletion lupus"
    python llm_extractor/extractor.py --query "CAR-T lupus" --model gpt-4o-mini --max 10
    python llm_extractor/extractor.py --query "JAK inhibitor" --export-html
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from med_research.pipeline.evidence.gatherer import gather_evidence

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = Path(__file__).parent / "data"
CACHE_PATH = DATA_DIR / "extraction_cache.json"

# ── Configuration ─────────────────────────────────────────────────────────

DEFAULT_MODEL = os.environ.get("LLM_EXTRACTOR_MODEL", "gpt-4o-mini")
API_BASE = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
API_KEY = os.environ.get("OPENAI_API_KEY")

EXTRACTION_SYSTEM_PROMPT = (
    "You are a biomedical evidence extraction AI. Extract structured information "
    "from the provided abstract/snippet of a biomedical research article. "
    "Respond ONLY with valid JSON — no markdown, no explanations, no code fences."
)

EXTRACTION_USER_PROMPT_TEMPLATE = """Extract structured data from this biomedical abstract. Return ONLY a JSON object with these fields:

- evidence_level: One of [meta-analysis, systematic_review, rct, observational_cohort, observational_case_control, case_series, case_report, preclinical_in_vivo, preclinical_in_vitro, computational_modeling, review_narrative, opinion, unknown]
- model_system: One of [human, murine, in_vitro, in_silico, ex_vivo, non_human_primate, mixed, unknown]
- key_findings: 1-3 sentence summary of the main result (max 400 chars)
- drugs_mentioned: List of drug/compound names mentioned, or empty list []
- disease: Primary disease or condition studied (max 100 chars)
- study_design: Study design type (e.g., double_blind_rct, open_label, retrospective, prospective_cohort, case_control, cross_sectional, preclinical, in_vitro, unknown)
- sample_size: Integer number of subjects/samples, or null if not stated
- p_value: String like "<0.001" or "0.03" or null
- effect_size: String like "HR=0.72" or null
- relevance_to_query: Score 0-100 how relevant the abstract is to the original search query
- confidence: Score 0-100 how confident you are in this extraction

Title: {title}
Source: {source} ({source_type})
Year: {year}
Abstract/Snippet: {snippet}

Original search query: {query}

JSON:"""


# ── Helpers ──────────────────────────────────────────────────────────────


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ── Cache ────────────────────────────────────────────────────────────────


def _cache_key(article_id: str, model: str) -> str:
    return f"{article_id}|||{model}"


def load_cache() -> dict:
    if CACHE_PATH.exists():
        return load_json(CACHE_PATH)
    return {}


def save_cache(cache: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    save_json(CACHE_PATH, cache)


# ── LLM API Call ─────────────────────────────────────────────────────────


def call_llm(
    system_prompt: str,
    user_prompt: str,
    model: str = None,
    temperature: float = 0.1,
    max_tokens: int = 800,
) -> str | None:
    """Call an OpenAI-compatible chat completions endpoint.

    Returns the message content string, or None on failure.
    """
    model = model or DEFAULT_MODEL

    if not API_KEY:
        print("  ⚠️  No OPENAI_API_KEY set. Set it to use LLM extraction.")
        return None

    url = f"{API_BASE.rstrip('/')}/chat/completions"

    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }

    try:
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=45) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return body["choices"][0]["message"]["content"].strip()
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError,
            KeyError, IndexError) as e:
        print(f"  ⚠️  LLM API error: {e}")
        return None


def _clean_json_response(text: str) -> str:
    """Strip markdown code fences and extract JSON from LLM response."""
    text = text.strip()
    # Remove ```json ... ``` fences
    if text.startswith("```"):
        lines = text.split("\n")
        # Drop first and last lines if they are fences
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    # Try to find JSON object bounds
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start:end + 1]
    return text


# ── Extraction Engine ────────────────────────────────────────────────────


def extract_evidence(
    article: dict,
    query: str,
    model: str = None,
    use_cache: bool = True,
) -> dict | None:
    """Extract structured data from a single evidence article using an LLM.

    Args:
        article: Evidence dict with title, snippet, source, source_type, year, id.
        query: The original search query for context.
        model: LLM model name (default: gpt-4o-mini).
        use_cache: Whether to use cached extractions.

    Returns:
        Dict with extracted fields, or None if extraction failed.
    """
    model = model or DEFAULT_MODEL
    article_id = article.get("id", article.get("title", ""))
    key = _cache_key(article_id, model)

    cache = load_cache()
    if use_cache and key in cache:
        return cache[key]

    user_prompt = EXTRACTION_USER_PROMPT_TEMPLATE.format(
        title=article.get("title", ""),
        source=article.get("source", ""),
        source_type=article.get("source_type", ""),
        year=article.get("year", ""),
        snippet=article.get("snippet", "")[:2000],
        query=query,
    )

    response = call_llm(EXTRACTION_SYSTEM_PROMPT, user_prompt, model)

    if response is None:
        # Return a minimal extraction with defaults
        extracted = {
            "evidence_level": "unknown",
            "model_system": "unknown",
            "key_findings": "",
            "drugs_mentioned": [],
            "disease": "",
            "study_design": "unknown",
            "sample_size": None,
            "p_value": None,
            "effect_size": None,
            "relevance_to_query": 50,
            "confidence": 0,
        }
        return extracted

    try:
        cleaned = _clean_json_response(response)
        extracted = json.loads(cleaned)
        # Ensure all expected fields exist
        defaults = {
            "evidence_level": "unknown",
            "model_system": "unknown",
            "key_findings": "",
            "drugs_mentioned": [],
            "disease": "",
            "study_design": "unknown",
            "sample_size": None,
            "p_value": None,
            "effect_size": None,
            "relevance_to_query": 50,
            "confidence": 0,
        }
        for field, default in defaults.items():
            if field not in extracted or extracted[field] is None:
                extracted[field] = default
    except (json.JSONDecodeError, ValueError) as e:
        print(f"  ⚠️  JSON parse error from LLM: {e}")
        extracted = {
            "evidence_level": "unknown",
            "model_system": "unknown",
            "key_findings": response[:400],
            "drugs_mentioned": [],
            "disease": "",
            "study_design": "unknown",
            "sample_size": None,
            "p_value": None,
            "effect_size": None,
            "relevance_to_query": 50,
            "confidence": 0,
        }

    cache[key] = extracted
    save_cache(cache)
    return extracted


def extract_all(
    query: str,
    sources: list = None,
    max_articles: int = 20,
    model: str = None,
    use_cache: bool = True,
) -> dict:
    """Gather evidence then extract structured data from all results.

    Args:
        query: Search query string.
        sources: List of source types (default: pubmed,preprints).
        max_articles: Max articles to extract from.
        model: LLM model name.
        use_cache: Whether to use cached results (both evidence + extractions).

    Returns:
        Dict with query, model, total_extracted, extractions list, and stats.
    """
    model = model or DEFAULT_MODEL
    if sources is None:
        sources = ["pubmed", "preprints", "clinical_trials"]

    if not API_KEY:
        print("\n⚠️  No OPENAI_API_KEY environment variable set.")
        print("   LLM extraction requires an API key.\n"
              "   Set it via: export OPENAI_API_KEY=sk-...\n"
              "   Or for local models (Ollama):\n"
              "     export OPENAI_API_KEY=ollama\n"
              "     export OPENAI_API_BASE=http://localhost:11434/v1\n"
              "     export LLM_EXTRACTOR_MODEL=llama3.1\n")
        return {
            "query": query,
            "model": model,
            "total_extracted": 0,
            "extractions": [],
            "stats": {},
            "error": "No API key configured.",
            "generated_at": datetime.now().isoformat(),
        }

    print(f"\n🤖 LLM Evidence Extractor — Model: {model}")
    print(f"   Query: \"{query}\"")
    print(f"   Sources: {', '.join(sources)}\n")

    # Step 1: Gather evidence
    print("Step 1/2: Gathering evidence...")
    evidence = gather_evidence(
        query,
        sources=sources,
        max_per_source=max_articles // len(sources) + 1,
        use_cache=use_cache,
    )
    articles = evidence["all_results"][:max_articles]
    print(f"   → {len(articles)} articles to extract\n")

    # Step 2: Extract structured data
    print("Step 2/2: Extracting structured data via LLM...")
    start_time = time.time()
    extractions = []
    success_count = 0

    for i, article in enumerate(articles, 1):
        print(f"  [{i}/{len(articles)}] {article['title'][:70]}...")
        extracted = extract_evidence(article, query, model, use_cache)
        if extracted:
            # Merge article metadata with extracted data
            extractions.append({
                "title": article.get("title", ""),
                "source_type": article.get("source_type", ""),
                "source": article.get("source", ""),
                "year": article.get("year", ""),
                "url": article.get("url", ""),
                "id": article.get("id", ""),
                "evidence_level": extracted.get("evidence_level", "unknown"),
                "model_system": extracted.get("model_system", "unknown"),
                "key_findings": extracted.get("key_findings", ""),
                "drugs_mentioned": extracted.get("drugs_mentioned", []),
                "disease": extracted.get("disease", ""),
                "study_design": extracted.get("study_design", "unknown"),
                "sample_size": extracted.get("sample_size"),
                "p_value": extracted.get("p_value"),
                "effect_size": extracted.get("effect_size"),
                "relevance_to_query": extracted.get("relevance_to_query", 50),
                "confidence": extracted.get("confidence", 0),
            })
            if extracted.get("confidence", 0) > 0:
                success_count += 1

    elapsed = time.time() - start_time

    # Compute stats
    stats = _compute_extraction_stats(extractions)

    output = {
        "query": query,
        "model": model,
        "total_extracted": len(extractions),
        "successful_extractions": success_count,
        "elapsed_seconds": round(elapsed, 1),
        "extractions": extractions,
        "stats": stats,
        "generated_at": datetime.now().isoformat(),
    }

    # Save results
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    save_json(DATA_DIR / "extraction_results.json", output)

    return output


def _compute_extraction_stats(extractions: list) -> dict:
    """Compute summary statistics across all extractions."""
    if not extractions:
        return {}

    # Evidence level distribution
    evidence_levels = {}
    model_systems = {}
    study_designs = {}
    drugs = set()
    diseases = {}
    total_sample = 0
    sample_count = 0
    avg_confidence = 0
    avg_relevance = 0

    for e in extractions:
        el = e.get("evidence_level", "unknown")
        evidence_levels[el] = evidence_levels.get(el, 0) + 1

        ms = e.get("model_system", "unknown")
        model_systems[ms] = model_systems.get(ms, 0) + 1

        sd = e.get("study_design", "unknown")
        study_designs[sd] = study_designs.get(sd, 0) + 1

        for drug in e.get("drugs_mentioned", []):
            drugs.add(drug)

        disease = e.get("disease", "")
        if disease:
            diseases[disease] = diseases.get(disease, 0) + 1

        if e.get("sample_size"):
            total_sample += e["sample_size"]
            sample_count += 1

        avg_confidence += e.get("confidence", 0)
        avg_relevance += e.get("relevance_to_query", 50)

    n = len(extractions)
    return {
        "evidence_levels": dict(sorted(evidence_levels.items(), key=lambda x: x[1], reverse=True)),
        "model_systems": dict(sorted(model_systems.items(), key=lambda x: x[1], reverse=True)),
        "study_designs": dict(sorted(study_designs.items(), key=lambda x: x[1], reverse=True)),
        "unique_drugs_mentioned": sorted(drugs),
        "n_unique_drugs": len(drugs),
        "top_diseases": dict(sorted(diseases.items(), key=lambda x: x[1], reverse=True)[:10]),
        "avg_sample_size": round(total_sample / sample_count) if sample_count else None,
        "articles_with_sample_size": sample_count,
        "avg_confidence": round(avg_confidence / n, 1),
        "avg_relevance": round(avg_relevance / n, 1),
    }


# ── CLI ──────────────────────────────────────────────────────────────────


def print_summary(results: dict):
    """Print a formatted summary of LLM extractions."""
    extractions = results.get("extractions", [])
    stats = results.get("stats", {})

    print("\n" + "=" * 75)
    print("🤖 LLM EVIDENCE EXTRACTION — Results")
    print("=" * 75)

    print(f"\n  Query: \"{results['query']}\"")
    print(f"  Model: {results['model']}")
    print(f"  Extracted: {results['total_extracted']} articles "
          f"({results['successful_extractions']} successful) "
          f"in {results['elapsed_seconds']}s")

    if stats:
        print("\n  📊 Evidence Level Distribution:")
        for level, count in stats.get("evidence_levels", {}).items():
            label = level.replace("_", " ").title()
            print(f"    {label:30s} {count}")

        print("\n  🧬 Model Systems:")
        for system, count in stats.get("model_systems", {}).items():
            label = system.replace("_", " ").title()
            print(f"    {label:30s} {count}")

        avg_conf = stats.get("avg_confidence", 0)
        avg_rel = stats.get("avg_relevance", 0)
        print(f"\n  📈 Avg Confidence: {avg_conf:.1f}%")
        print(f"  📈 Avg Relevance: {avg_rel:.1f}%")

        if stats.get("n_unique_drugs", 0) > 0:
            print(f"\n  💊 Drugs Mentioned ({stats['n_unique_drugs']}): "
                  f"{', '.join(stats['unique_drugs_mentioned'][:12])}")

    print("\n  📋 Top Extractions:")
    # Sort by relevance * confidence
    scored = sorted(extractions, key=lambda x: x.get("relevance_to_query", 50) * x.get("confidence", 0) / 10000, reverse=True)
    for i, e in enumerate(scored[:10], 1):
        level = e.get("evidence_level", "?").replace("_", " ").title()
        system = e.get("model_system", "?").replace("_", " ").title()
        finding = e.get("key_findings", "")[:100]
        print(f"  {i:2d}. [{level}] [{system}] {finding}")


def main():
    parser = argparse.ArgumentParser(
        description="LLM Evidence Extractor — Structured data extraction from biomedical abstracts"
    )
    parser.add_argument("--query", "-q", type=str, default="B cell depletion therapy lupus",
                        help="Search query (natural language)")
    parser.add_argument("--sources", type=str, default="pubmed,preprints,clinical_trials",
                        help="Comma-separated evidence sources")
    parser.add_argument("--model", "-m", type=str, default=DEFAULT_MODEL,
                        help=f"LLM model name (default: {DEFAULT_MODEL})")
    parser.add_argument("--max", type=int, default=20, dest="max_articles",
                        help="Max articles to extract from (default: 20)")
    parser.add_argument("--no-cache", action="store_true",
                        help="Skip cache, re-extract everything")
    parser.add_argument("--top", type=int, default=15,
                        help="Number of top results to display")
    parser.add_argument("--export-html", action="store_true",
                        help="Generate HTML report")

    args = parser.parse_args()

    sources = [s.strip() for s in args.sources.split(",")]

    results = extract_all(
        args.query,
        sources=sources,
        max_articles=args.max_articles,
        model=args.model,
        use_cache=not args.no_cache,
    )

    if "error" not in results:
        print_summary(results)

    if args.export_html and "error" not in results:
        from med_research.pipeline.evidence.report import generate_html_report
        generate_html_report(results)
        print("\n✅ HTML report generated: llm_extractor/report.html")

    return results


if __name__ == "__main__":
    main()
