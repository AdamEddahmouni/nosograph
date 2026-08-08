"""
Lupus Clinical Trial Tracker

Queries ClinicalTrials.gov API v2 for lupus/SLE interventional trials,
categorizes by phase, mechanism of action, and sponsor, and
cross-references trial drugs against the Lupus Knowledge Graph.

API: https://clinicaltrials.gov/api/v2
No API key required.

Usage:
    python tracker.py                          # Full tracking
    python tracker.py --max 100 --export-html  # 100 trials + HTML report
"""

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from med_research.rate_limiter import rate_limited_sleep

sys.path.insert(0, str(Path(__file__).parent.parent))

import logging

from med_research.cache import NS_CLINICAL_TRIALS, cache_get, cache_set, load_legacy_json
from med_research.exceptions import (
    DataValidationError,
    ExternalAPIError,
    classify_api_error,
    retry_with_backoff,
)
from med_research.pipeline.knowledge_graph.config import load_drugs as config_load_drugs
from med_research.pipeline.knowledge_graph.config import load_genes as config_load_genes
from med_research.pipeline.progress import StandardProgress, _tick

logger = logging.getLogger(__name__)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = Path(__file__).parent / "data"
last_coverage = None

# ClinicalTrials.gov API v2
CT_API = "https://clinicaltrials.gov/api/v2"


def _ct_http_get(params: dict):
    """Perform a ClinicalTrials.gov GET request, raising on HTTP failure."""
    resp = requests.get(f"{CT_API}/studies", params=params, timeout=30)
    resp.raise_for_status()
    return resp


# Phase ordering for sorting
PHASE_ORDER = {
    "EARLY_PHASE1": 0,
    "PHASE1": 1,
    "PHASE2": 2,
    "PHASE3": 3,
    "PHASE4": 4,
}

PHASE_LABELS = {
    "EARLY_PHASE1": "Early Phase 1",
    "PHASE1": "Phase 1",
    "PHASE2": "Phase 2",
    "PHASE3": "Phase 3",
    "PHASE4": "Phase 4",
}

# Mechanism of action keywords for categorization
MOA_KEYWORDS = {
    "Cell Therapy": ["car-t", "car t", "stem cell", "mesenchymal", "cellular therapy"],
    "B Cell Targeting": ["b cell", "cd20", "cd19", "baff", "blys", "btk", "b-cell", "cd22"],
    "T Cell / Costimulation": ["t cell", "cd40", "icos", "calcineurin", "t-cell", "cd28"],
    "Type I IFN / JAK-STAT": ["interferon", "ifn", "jak", "tyk2", "ifnar", "stat"],
    "Complement": ["complement", "c5", "c5a", "factor b", "factor d"],
    "Cytokine / Chemokine": ["cytokine", "il-", "interleukin", "tnf", "chemokine", "il6", "il17"],
    "Plasma Cell / Proteasome": ["plasma cell", "proteasome", "bcma", "bortezomib"],
    "Immunomodulator": ["immunomodulator", "immunomodulatory", "hydroxychloroquine", "antimalarial"],
    "Anti-inflammatory": ["anti-inflammatory", "corticosteroid", "steroid", "prednisone"],
    "Other Targeted": [],
}


def search_clinical_trials(
    query: str,
    max_results: int = 100,
    progress_callback: StandardProgress | None = None,
) -> list:
    """Search ClinicalTrials.gov API v2 for trials matching the query.

    Returns list of study dicts with protocolSection data.
    """
    if not REQUESTS_AVAILABLE:
        logger.info("❌ requests required. Install: pip install requests")
        return []

    all_studies = []
    page_token = None

    fields = (
        "NCTId|BriefTitle|OfficialTitle|OverallStatus|Phase|"
        "Condition|InterventionName|InterventionType|"
        "LeadSponsorName|LeadSponsorClass|"
        "EnrollmentCount|EnrollmentType|"
        "StartDate|PrimaryCompletionDate|"
        "WhyStopped|"
        "BriefSummary|"
        "StudyType"
    )

    logger.info(f"\n🔍 Searching ClinicalTrials.gov for: {query}")

    while len(all_studies) < max_results:
        params = {
            "query.cond": query,
            "query.term": "AREA[StudyType]INTERVENTIONAL",
            "pageSize": min(100, max_results - len(all_studies)),
            "fields": fields,
            "format": "json",
        }

        if page_token:
            params["pageToken"] = page_token

        try:
            resp = retry_with_backoff(
                lambda p=params: _ct_http_get(p),
                source="ClinicalTrials.gov search",
            )
            data = resp.json()
        except (ExternalAPIError, requests.exceptions.RequestException, json.JSONDecodeError) as e:
            err = classify_api_error(e, "ClinicalTrials.gov search")
            logger.info(f"   ⚠️  {err}")
            break

        studies = data.get("studies", [])
        all_studies.extend(studies)
        _tick(
            progress_callback,
            "fetching clinical trials",
            min(len(all_studies), max_results),
            max_results,
        )

        page_token = data.get("nextPageToken")
        if not page_token or len(studies) == 0:
            break

        rate_limited_sleep(0.3)

    logger.info(f"   Found {len(all_studies)} interventional trials")
    return all_studies


def parse_trial(study: dict) -> dict:
    """Parse a ClinicalTrials.gov study into a structured format."""
    proto = study.get("protocolSection", {})

    # Identification
    ident = proto.get("identificationModule", {})
    nct_id = ident.get("nctId", study.get("nctId", ""))

    # Status
    status_mod = proto.get("statusModule", {})
    status = status_mod.get("overallStatus", "UNKNOWN")

    # Brief info
    brief = proto.get("descriptionModule", {})
    title = brief.get("briefTitle", "Unknown")
    summary = brief.get("briefSummary", "")

    # Design
    design = proto.get("designModule", {})
    phases = design.get("phases", [])
    enrollment = design.get("enrollmentInfo", {})
    enrollment_count = enrollment.get("count", 0) if enrollment else 0

    # Interventions
    interventions_mod = proto.get("armsInterventionsModule", {})
    interventions = interventions_mod.get("interventions", [])
    intervention_names = []
    intervention_types = []
    for iv in interventions:
        name = iv.get("name", "")
        itype = iv.get("type", "")
        if name:
            intervention_names.append(name)
        if itype:
            intervention_types.append(itype)

    # Sponsor
    sponsor_mod = proto.get("sponsorCollaboratorsModule", {})
    lead_sponsor = sponsor_mod.get("leadSponsor", {})
    sponsor_name = lead_sponsor.get("name", "Unknown")
    sponsor_class = lead_sponsor.get("class", "UNKNOWN")

    # Dates
    start_date = proto.get("startDateStruct", {}).get("date", "") if "startDateStruct" in proto else ""
    completion_date = ""
    if "primaryCompletionDateStruct" in proto:
        completion_date = proto["primaryCompletionDateStruct"].get("date", "")

    # Why stopped (for terminated/withdrawn trials)
    why_stopped = status_mod.get("whyStopped", "")

    # Conditions
    conditions_mod = proto.get("conditionsModule", {})
    conditions = conditions_mod.get("conditions", [])

    return {
        "nct_id": nct_id,
        "title": title,
        "summary": summary[:500] if summary else "",
        "status": status,
        "phases": phases,
        "primary_phase": _primary_phase(phases),
        "phase_label": PHASE_LABELS.get(_primary_phase(phases), "Unknown"),
        "interventions": intervention_names,
        "intervention_types": intervention_types,
        "sponsor_name": sponsor_name,
        "sponsor_class": sponsor_class,
        "enrollment": enrollment_count,
        "start_date": start_date,
        "completion_date": completion_date,
        "why_stopped": why_stopped,
        "conditions": conditions,
    }


def _primary_phase(phases: list) -> str:
    """Get the highest/latest phase from a list of phases."""
    if not phases:
        return ""
    best = "PHASE1"
    for p in phases:
        if PHASE_ORDER.get(p, -1) > PHASE_ORDER.get(best, -1):
            best = p
    return best


def categorize_moa(trial: dict) -> str:
    """Categorize a trial's mechanism of action from its interventions and title."""
    text = (trial.get("title", "") + " " +
            " ".join(trial.get("interventions", []))).lower()

    for category, keywords in MOA_KEYWORDS.items():
        if category == "Other Targeted":
            continue
        for kw in keywords:
            if kw in text:
                return category

    # Check if any keyword matches in summary
    summary = trial.get("summary", "").lower()
    for category, keywords in MOA_KEYWORDS.items():
        if category == "Other Targeted":
            continue
        for kw in keywords:
            if kw in summary:
                return category

    return "Other Targeted"


def _legacy_ct_cache_path(disease_id: str, query_key: str) -> Path:
    """Legacy per-query clinical trial cache path (read-only after migration)."""
    return DATA_DIR / f"ct_cache_{disease_id}_{query_key}.json"


def _get_cached_trials(disease_id: str, query_key: str, use_cache: bool) -> dict | None:
    """Load trial payload from CacheManager namespace, falling back to legacy file once."""
    lookup_key = f"{disease_id}|||{query_key}"
    cached = cache_get(NS_CLINICAL_TRIALS, lookup_key, use_cache=use_cache)
    if cached is not None:
        return cached
    if not use_cache:
        return None
    legacy = load_legacy_json(_legacy_ct_cache_path(disease_id, query_key))
    if legacy:
        cache_set(NS_CLINICAL_TRIALS, lookup_key, legacy, use_cache=True)
        return legacy
    return None


def load_kg_entities(disease_id: str = "sle") -> dict:
    """Load disease-specific KG genes and drugs for cross-referencing."""
    genes = {}
    try:
        genes_data = config_load_genes(disease_id)
        for g in genes_data["genes"]:
            genes[g["id"]] = g
    except (DataValidationError, FileNotFoundError, json.JSONDecodeError) as exc:
        logger.debug("Could not load KG genes for trial cross-reference: %s", exc)

    drugs = {}
    try:
        drugs_data = config_load_drugs(disease_id)
        for d in drugs_data["drugs"]:
            drugs[d["id"]] = d
    except (DataValidationError, FileNotFoundError, json.JSONDecodeError) as exc:
        logger.debug("Could not load KG drugs for trial cross-reference: %s", exc)

    return {"genes": genes, "drugs": drugs}


def cross_reference_trials(trials: list, kg_entities: dict) -> list:
    """Cross-reference trial interventions against KG genes and drugs."""
    results = []

    for trial in trials:
        matched_genes = []
        matched_drugs = []

        text = (trial.get("title", "") + " " +
                " ".join(trial.get("interventions", [])) + " " +
                trial.get("summary", "")).lower()

        # Match against KG genes
        for gene_id, gene in kg_entities["genes"].items():
            gene_name = gene["name"].lower()
            # Match by gene ID (e.g. "BTK", "JAK1") or partial name
            if (
                (gene_id.lower() in text or any(
                    part.lower() in text for part in gene_name.split() if len(part) > 4
                ))
                and gene_id not in [g["gene_id"] for g in matched_genes]
            ):
                    matched_genes.append({
                        "gene_id": gene_id,
                        "gene_name": gene["name"],
                        "category": gene.get("category", ""),
                    })

        # Match against KG drugs
        for drug_id, drug in kg_entities["drugs"].items():
            drug_name = drug["name"].lower().split("(")[0].strip()
            if (
                (drug_name in text or drug_id in text)
                and drug_id not in [d["drug_id"] for d in matched_drugs]
            ):
                    matched_drugs.append({
                        "drug_id": drug_id,
                        "drug_name": drug["name"],
                        "target": drug.get("target", ""),
                        "category": drug.get("category", ""),
                    })

        trial["kg_matches"] = {
            "genes": matched_genes,
            "drugs": matched_drugs,
            "gene_count": len(matched_genes),
            "drug_count": len(matched_drugs),
            "has_match": len(matched_genes) > 0 or len(matched_drugs) > 0,
        }
        results.append(trial)

    return results


def track_trials(
    query: str = "",
    max_results: int = 100,
    use_cache: bool = True,
    disease_id: str = "sle",
    progress_callback: StandardProgress | None = None,
) -> dict:
    """Run the full clinical trial tracking pipeline.

    Returns:
        dict with trials, stats, and kg_crossref data.
    """
    from med_research.diseases.coverage import module_coverage

    global last_coverage
    coverage = module_coverage(
        disease_id, "clinical_trials", ("genes", "drugs", "trial_query")
    )
    last_coverage = coverage
    if not coverage.is_runnable:
        logger.error(
            "Clinical trials blocked for %s: %s",
            disease_id,
            ", ".join(coverage.missing_inputs),
        )
        return {
            "trials": [],
            "stats": {},
            "kg_crossref": {},
            "coverage": coverage.to_dict(),
            "status": "blocked",
        }

    if not query:
        from med_research.diseases.base import Disease

        query = Disease(disease_id).get_trial_query()

    # Load KG
    logger.info("🔄 Loading knowledge graph entities...")
    kg_entities = load_kg_entities(disease_id)
    logger.info(f"   Loaded {len(kg_entities['genes'])} genes, {len(kg_entities['drugs'])} drugs")

    # Cache is namespaced by disease and query so results cannot bleed across KGs.
    import hashlib
    query_key = hashlib.sha256(f"{disease_id}|{query}".encode()).hexdigest()[:12]
    cache_lookup_key = f"{disease_id}|||{query_key}"

    cached_payload = _get_cached_trials(disease_id, query_key, use_cache)

    if use_cache and cached_payload is not None:
        try:
            trials = cached_payload.get("trials", [])
            if len(trials) >= max_results:
                logger.info(f"📦 Loading {len(trials)} trials from cache...")
                _tick(progress_callback, "loading clinical trials", 1, 1)
                if cached_payload.get("kg_crossref"):
                    trials = [dict(t) for t in trials]
                    for t in trials:
                        if "kg_matches" not in t:
                            t["kg_matches"] = {
                                "genes": [],
                                "drugs": [],
                                "gene_count": 0,
                                "drug_count": 0,
                                "has_match": False,
                            }
                    return {
                        "trials": trials,
                        "stats": _compute_stats(trials),
                        "kg_crossref": cached_payload.get("kg_crossref", {}),
                    }
        except (KeyError, TypeError) as e:
            logger.info(f"   ⚠️  Cache error ({e}), re-fetching...")

    # Search trials
    raw_trials = search_clinical_trials(
        query,
        max_results,
        progress_callback=progress_callback,
    )

    # Parse trials
    trials = []
    for i, trial in enumerate(raw_trials, 1):
        _tick(progress_callback, "parsing trials", i, len(raw_trials))
        trials.append(parse_trial(trial))

    # Categorize MoA
    for trial in trials:
        trial["moa_category"] = categorize_moa(trial)

    # Cross-reference with KG
    logger.info("🔄 Cross-referencing against knowledge graph...")
    trials = cross_reference_trials(trials, kg_entities)

    # Compute stats
    stats = _compute_stats(trials)

    # Build crossref summary
    kg_crossref = _build_crossref_summary(trials)

    # Cache
    cache_data = {
        "trials": trials,
        "stats": stats,
        "kg_crossref": kg_crossref,
        "timestamp": datetime.now().isoformat(),
    }
    cache_set(NS_CLINICAL_TRIALS, cache_lookup_key, cache_data, use_cache=use_cache)
    logger.info("💾 Cached %d trials (namespace=%s)", len(trials), NS_CLINICAL_TRIALS)

    return {"trials": trials, "stats": stats, "kg_crossref": kg_crossref}


def _compute_stats(trials: list) -> dict:
    """Compute summary statistics across all trials."""
    statuses = Counter(t["status"] for t in trials)
    phases = Counter()
    moas = Counter()
    sponsors = Counter()
    matched_count = 0
    total_enrollment = 0
    enrollment_count = 0

    for t in trials:
        for p in t.get("phases", []):
            phases[PHASE_LABELS.get(p, p)] += 1
        moas[t.get("moa_category", "Other")] += 1
        sponsors[t.get("sponsor_name", "Unknown")] += 1
        if t.get("kg_matches", {}).get("has_match"):
            matched_count += 1
        if t.get("enrollment"):
            total_enrollment += t["enrollment"]
            enrollment_count += 1

    return {
        "total_trials": len(trials),
        "statuses": dict(statuses.most_common()),
        "phases": dict(phases.most_common()),
        "moas": dict(moas.most_common()),
        "top_sponsors": dict(sponsors.most_common(10)),
        "kg_matched_trials": matched_count,
        "total_enrollment": total_enrollment,
        "avg_enrollment": round(total_enrollment / enrollment_count) if enrollment_count else 0,
    }


def _build_crossref_summary(trials: list) -> dict:
    """Build a summary of KG cross-references across all trials."""
    gene_hits = Counter()
    drug_hits = Counter()
    trials_with_matches = []

    for t in trials:
        kg = t.get("kg_matches", {})
        if kg.get("has_match"):
            trials_with_matches.append({
                "nct_id": t["nct_id"],
                "title": t["title"][:100],
                "phase": t["phase_label"],
                "status": t["status"],
                "gene_count": kg["gene_count"],
                "drug_count": kg["drug_count"],
                "genes": [g["gene_id"] for g in kg.get("genes", [])],
                "drugs": [d["drug_id"] for d in kg.get("drugs", [])],
                "moa": t.get("moa_category", ""),
            })
        for g in kg.get("genes", []):
            gene_hits[g["gene_id"]] += 1
        for d in kg.get("drugs", []):
            drug_hits[d["drug_id"]] += 1

    return {
        "gene_hits": dict(gene_hits.most_common(20)),
        "drug_hits": dict(drug_hits.most_common(20)),
        "trials_with_matches": trials_with_matches,
        "total_matched": len(trials_with_matches),
    }


def print_summary(stats: dict, kg_crossref: dict):
    """Print a summary of clinical trial tracking results."""
    logger.info("\n" + "=" * 70)
    logger.info("📋 CLINICAL TRIAL TRACKER RESULTS")
    logger.info("=" * 70)

    logger.info(f"\n  Total trials analyzed:      {stats['total_trials']}")
    logger.info(f"  KG-matched trials:          {stats['kg_matched_trials']}")
    logger.info(f"  Total enrollment:           {stats['total_enrollment']:,}")
    logger.info(f"  Avg enrollment:             {stats['avg_enrollment']:,}")

    # Phases
    logger.info("\n  📊 Phase distribution:")
    for phase, count in sorted(stats["phases"].items(),
                                key=lambda x: PHASE_ORDER.get(
                                    {v: k for k, v in PHASE_LABELS.items()}.get(x[0], ""), -1
                                )):
        bar_width = int(count / max(stats["phases"].values()) * 30) if stats["phases"] else 0
        logger.info(f"    {phase:<16} {'█' * bar_width} {count}")

    # MoA
    moas = stats.get("moas", {})
    if moas:
        logger.info("\n  🔬 Mechanism of action categories:")
        for moa, count in sorted(moas.items(), key=lambda x: x[1], reverse=True)[:8]:
            logger.info(f"    • {moa:<30} {count}")

    # Top sponsors
    sponsors = stats.get("top_sponsors", {})
    if sponsors:
        logger.info("\n  🏢 Top sponsors:")
        for sponsor, count in sorted(sponsors.items(), key=lambda x: x[1], reverse=True)[:5]:
            logger.info(f"    • {sponsor[:55]:<57} {count}")

    # KG crossref
    gene_hits = kg_crossref.get("gene_hits", {})
    if gene_hits:
        logger.info("\n  🧬 Top genes in clinical trials:")
        for gene_id, count in list(gene_hits.items())[:8]:
            logger.info(f"    • {gene_id:<30} {count} trial{'s' if count > 1 else ''}")

    drug_hits = kg_crossref.get("drug_hits", {})
    if drug_hits:
        logger.info("\n  💊 Top drugs in clinical trials:")
        for drug_id, count in list(drug_hits.items())[:8]:
            logger.info(f"    • {drug_id:<30} {count} trial{'s' if count > 1 else ''}")


def main():
    parser = argparse.ArgumentParser(
        description="Lupus Clinical Trial Tracker — ClinicalTrials.gov analysis"
    )
    parser.add_argument(
        "--max", type=int, default=100,
        help="Max trials to fetch (default: 100)",
    )
    parser.add_argument(
        "--query", type=str, default="",
        help="Query for ClinicalTrials.gov (default: disease config query)",
    )
    parser.add_argument(
        "--disease", "-d", default="sle", help="Disease ID (default: sle)"
    )
    parser.add_argument(
        "--no-cache", action="store_true",
        help="Skip cache, re-fetch from ClinicalTrials.gov",
    )
    parser.add_argument(
        "--export-html", action="store_true",
        help="Generate HTML report",
    )
    args = parser.parse_args()

    logger.info("🔄 Initializing Clinical Trial Tracker...")
    results = track_trials(
        query=args.query,
        max_results=args.max,
        use_cache=not args.no_cache,
        disease_id=args.disease,
    )

    print_summary(results["stats"], results["kg_crossref"])

    # Save results
    output_path = DATA_DIR / "ct_results.json"
    output_path.write_text(
        json.dumps(results, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    logger.info(f"\n💾 Results saved to {output_path}")

    if args.export_html:
        from med_research.diseases.base import Disease
        from med_research.pipeline.clinical_trials.report import generate_ct_report
        from med_research.pipeline.provenance import build_provenance

        query = args.query or Disease(args.disease).get_trial_query()
        provenance = build_provenance(
            disease_id=args.disease,
            module="clinical_trials",
            sources=["clinicaltrials_gov"],
            query=query,
            cache_or_live="cache" if not args.no_cache else "live",
        )
        report_path = generate_ct_report(
            results, disease_id=args.disease, provenance=provenance
        )
        logger.info(f"✅ HTML report generated: {report_path}")

    return results


if __name__ == "__main__":
    results = main()
