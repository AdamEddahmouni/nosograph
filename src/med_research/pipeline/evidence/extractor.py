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
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).parent.parent))

import logging

from med_research.cache import NS_LLM_EXTRACTOR, cache_get, cache_set, load_legacy_json
from med_research.exceptions import ExternalAPIError, classify_api_error, retry_with_backoff
from med_research.pipeline.evidence.gatherer import gather_evidence
from med_research.pipeline.progress import StandardProgress, _tick, cli_progress
from med_research.pipeline.results import EvidenceExtractionResult

logger = logging.getLogger(__name__)
if sys.platform == "win32":
    _stdout = sys.stdout
    if hasattr(_stdout, "reconfigure"):
        _stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = Path(__file__).parent / "data"
LEGACY_EXTRACTION_CACHE = DATA_DIR / "extraction_cache.json"
CACHE_PATH = LEGACY_EXTRACTION_CACHE  # backward compat for tests; not written after migration

# ── Configuration ─────────────────────────────────────────────────────────

DEFAULT_MODEL = os.environ.get("LLM_EXTRACTOR_MODEL", "gpt-4o-mini")
API_BASE = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
API_KEY = os.environ.get("OPENAI_API_KEY")

last_coverage = None

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
        return cast(dict, json.load(f))


def save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ── Cache ────────────────────────────────────────────────────────────────


def _cache_key(article_id: str, model: str) -> str:
    return f"{article_id}|||{model}"


def _load_legacy_extraction_cache() -> dict:
    legacy = load_legacy_json(LEGACY_EXTRACTION_CACHE)
    return legacy if isinstance(legacy, dict) else {}


def _get_cached_extraction(key: str, use_cache: bool) -> dict | None:
    cached = cache_get(NS_LLM_EXTRACTOR, key, use_cache=use_cache)
    if cached is not None:
        return cast(dict, cached)
    if not use_cache:
        return None
    legacy = _load_legacy_extraction_cache()
    if key in legacy:
        cache_set(NS_LLM_EXTRACTOR, key, legacy[key], use_cache=True)
        return cast(dict, legacy[key])
    return None


def _set_cached_extraction(key: str, extracted: dict, use_cache: bool) -> None:
    cache_set(NS_LLM_EXTRACTOR, key, extracted, use_cache=use_cache)


# ── LLM API Call ─────────────────────────────────────────────────────────


def call_llm(
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    temperature: float = 0.1,
    max_tokens: int = 800,
) -> str | None:
    """Call an OpenAI-compatible chat completions endpoint.

    Returns the message content string, or None on failure.
    """
    model = model or DEFAULT_MODEL

    if not API_KEY:
        logger.info("  ⚠️  No OPENAI_API_KEY set. Set it to use LLM extraction.")
        return None

    url = f"{API_BASE.rstrip('/')}/chat/completions"

    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
    ).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }

    def _call() -> str:
        try:
            return _call_llm_request(url, payload, headers)
        except json.JSONDecodeError as e:
            raise classify_api_error(e, "LLM chat completions response parse") from e
        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            raise classify_api_error(e, "LLM chat completions") from e
        except (KeyError, IndexError, ValueError) as e:
            raise classify_api_error(e, "LLM chat completions response") from e

    try:
        return retry_with_backoff(_call, source="LLM chat completions")
    except ExternalAPIError as e:
        logger.info(f"  ⚠️  {e}")
        return None


def _call_llm_request(url: str, payload: bytes, headers: dict) -> str:
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=45) as resp:
        body = json.loads(resp.read().decode("utf-8"))
        return cast(str, body["choices"][0]["message"]["content"]).strip()


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
        text = text[start : end + 1]
    return text


# ── Extraction Engine ────────────────────────────────────────────────────


def extract_evidence(
    article: dict,
    query: str,
    model: str | None = None,
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

    cached = _get_cached_extraction(key, use_cache)
    if cached is not None:
        return cached

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
        extracted: dict[str, Any] = {
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
        defaults: dict[str, Any] = {
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
        logger.info(f"  ⚠️  JSON parse error from LLM: {e}")
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

    _set_cached_extraction(key, extracted, use_cache)
    return extracted


def extract_all(
    query: str,
    sources: list | None = None,
    max_articles: int = 20,
    model: str | None = None,
    use_cache: bool = True,
    disease_id: str | None = None,
    progress_callback: StandardProgress | None = None,
) -> EvidenceExtractionResult:
    """Gather evidence then extract structured data from all results.

    Args:
        query: Search query string.
        sources: List of source types (default: pubmed,preprints).
        max_articles: Max articles to extract from.
        model: LLM model name.
        use_cache: Whether to use cached results (both evidence + extractions).
        disease_id: Optional disease scope for gather coverage checks.

    Returns:
        Dict with query, model, total_extracted, extractions list, and stats.
    """
    from med_research.diseases.coverage import module_coverage

    model = model or DEFAULT_MODEL
    global last_coverage
    last_coverage = module_coverage(
        disease_id or "global",
        "evidence_extract",
        (),
    )
    if not last_coverage.is_runnable:
        _tick(progress_callback, "llm extraction blocked", 1, 1)
        return {
            "query": query,
            "model": model,
            "total_extracted": 0,
            "successful_extractions": 0,
            "elapsed_seconds": 0.0,
            "extractions": [],
            "stats": {},
            "coverage": last_coverage.to_dict(),
            "status": "blocked",
            "error": "LLM extraction blocked: OPENAI_API_KEY is not configured.",
            "generated_at": datetime.now().isoformat(),
        }

    if sources is None:
        sources = ["pubmed", "preprints", "clinical_trials"]

    if not API_KEY:
        _tick(progress_callback, "llm extraction blocked", 1, 1)
        logger.info("\n⚠️  No OPENAI_API_KEY environment variable set.")
        logger.info(
            "   LLM extraction requires an API key.\n"
            "   Set it via: export OPENAI_API_KEY=sk-...\n"
            "   Or for local models (Ollama):\n"
            "     export OPENAI_API_KEY=ollama\n"
            "     export OPENAI_API_BASE=http://localhost:11434/v1\n"
            "     export LLM_EXTRACTOR_MODEL=llama3.1\n"
        )
        return {
            "query": query,
            "model": model,
            "total_extracted": 0,
            "successful_extractions": 0,
            "elapsed_seconds": 0.0,
            "extractions": [],
            "stats": {},
            "coverage": last_coverage.to_dict(),
            "status": "blocked",
            "error": "No API key configured.",
            "generated_at": datetime.now().isoformat(),
        }

    logger.info(f"\n🤖 LLM Evidence Extractor — Model: {model}")
    logger.info(f'   Query: "{query}"')
    logger.info(f"   Sources: {', '.join(sources)}\n")

    # Step 1: Gather evidence
    logger.info("Step 1/2: Gathering evidence...")
    _tick(progress_callback, "gathering evidence", 0, 2)
    evidence = gather_evidence(
        query,
        sources=sources,
        max_per_source=max_articles // len(sources) + 1,
        use_cache=use_cache,
        disease_id=disease_id,
        progress_callback=progress_callback,
    )
    articles = evidence["all_results"][:max_articles]
    _tick(progress_callback, "gathering evidence", 1, 2)
    logger.info(f"   → {len(articles)} articles to extract\n")

    # Step 2: Extract structured data
    logger.info("Step 2/2: Extracting structured data via LLM...")
    start_time = time.time()
    extractions = []
    success_count = 0

    for i, article in enumerate(articles, 1):
        _tick(progress_callback, "extracting evidence", i, len(articles) or 1)
        logger.info(f"  [{i}/{len(articles)}] {article['title'][:70]}...")
        extracted = extract_evidence(article, query, model, use_cache)
        if extracted:
            # Merge article metadata with extracted data
            extractions.append(
                {
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
                }
            )
            if extracted.get("confidence", 0) > 0:
                success_count += 1

    elapsed = time.time() - start_time

    # Compute stats
    stats = _compute_extraction_stats(extractions)

    output: EvidenceExtractionResult = {
        "query": query,
        "model": model,
        "total_extracted": len(extractions),
        "successful_extractions": success_count,
        "elapsed_seconds": round(elapsed, 1),
        "extractions": extractions,
        "stats": stats,
        "generated_at": datetime.now().isoformat(),
        "coverage": last_coverage.to_dict(),
        "status": "ready",
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
    evidence_levels: dict[str, int] = {}
    model_systems: dict[str, int] = {}
    study_designs: dict[str, int] = {}
    drugs: set[str] = set()
    diseases: dict[str, int] = {}
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


def print_summary(results: EvidenceExtractionResult) -> None:
    """Print a formatted summary of LLM extractions."""
    extractions = results.get("extractions", [])
    stats = results.get("stats", {})

    logger.info("\n" + "=" * 75)
    logger.info("🤖 LLM EVIDENCE EXTRACTION — Results")
    logger.info("=" * 75)

    logger.info(f'\n  Query: "{results["query"]}"')
    logger.info(f"  Model: {results['model']}")
    logger.info(
        f"  Extracted: {results['total_extracted']} articles "
        f"({results['successful_extractions']} successful) "
        f"in {results['elapsed_seconds']}s"
    )

    if stats:
        logger.info("\n  📊 Evidence Level Distribution:")
        for level, count in stats.get("evidence_levels", {}).items():
            label = level.replace("_", " ").title()
            logger.info(f"    {label:30s} {count}")

        logger.info("\n  🧬 Model Systems:")
        for system, count in stats.get("model_systems", {}).items():
            label = system.replace("_", " ").title()
            logger.info(f"    {label:30s} {count}")

        avg_conf = stats.get("avg_confidence", 0)
        avg_rel = stats.get("avg_relevance", 0)
        logger.info(f"\n  📈 Avg Confidence: {avg_conf:.1f}%")
        logger.info(f"  📈 Avg Relevance: {avg_rel:.1f}%")

        if stats.get("n_unique_drugs", 0) > 0:
            logger.info(
                f"\n  💊 Drugs Mentioned ({stats['n_unique_drugs']}): "
                f"{', '.join(stats['unique_drugs_mentioned'][:12])}"
            )

    logger.info("\n  📋 Top Extractions:")
    # Sort by relevance * confidence
    scored = sorted(
        extractions,
        key=lambda x: x.get("relevance_to_query", 50) * x.get("confidence", 0) / 10000,
        reverse=True,
    )
    for i, e in enumerate(scored[:10], 1):
        level = e.get("evidence_level", "?").replace("_", " ").title()
        system = e.get("model_system", "?").replace("_", " ").title()
        finding = e.get("key_findings", "")[:100]
        logger.info(f"  {i:2d}. [{level}] [{system}] {finding}")


def main():
    parser = argparse.ArgumentParser(
        description="LLM Evidence Extractor — Structured data extraction from biomedical abstracts"
    )
    parser.add_argument(
        "--query",
        "-q",
        type=str,
        default="B cell depletion therapy lupus",
        help="Search query (natural language)",
    )
    parser.add_argument(
        "--sources",
        type=str,
        default="pubmed,preprints,clinical_trials",
        help="Comma-separated evidence sources",
    )
    parser.add_argument(
        "--model",
        "-m",
        type=str,
        default=DEFAULT_MODEL,
        help=f"LLM model name (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=20,
        dest="max_articles",
        help="Max articles to extract from (default: 20)",
    )
    parser.add_argument("--no-cache", action="store_true", help="Skip cache, re-extract everything")
    parser.add_argument("--top", type=int, default=15, help="Number of top results to display")
    parser.add_argument("--export-html", action="store_true", help="Generate HTML report")

    args = parser.parse_args()

    sources = [s.strip() for s in args.sources.split(",")]

    results = extract_all(
        args.query,
        sources=sources,
        max_articles=args.max_articles,
        model=args.model,
        use_cache=not args.no_cache,
        progress_callback=cli_progress,
    )

    if "error" not in results:
        print_summary(results)

    if args.export_html and "error" not in results:
        from med_research.pipeline.evidence.extractor_report import generate_html_report
        from med_research.pipeline.provenance import build_provenance

        provenance = build_provenance(
            disease_id="query",
            module="llm_extractor",
            sources=sources,
            query=args.query,
            cache_or_live="live" if args.no_cache else "cache",
            model=args.model,
        )
        generate_html_report(cast(dict, results), provenance=provenance)
        logger.info("\n✅ HTML report generated: llm_extractor/report.html")

    return results


if __name__ == "__main__":
    import sys

    from med_research.cli import main as cli_main

    sys.exit(cli_main() or 0)

