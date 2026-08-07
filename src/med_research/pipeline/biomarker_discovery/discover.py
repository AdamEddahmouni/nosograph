"""
Biomarker Discovery Engine — Cross-Module Integration

Correlates gene expression signatures with predicted treatment responses
across all 5 scoring platforms to identify the most predictive biomarkers
for lupus therapy selection.

Scoring Dimensions (each 0-10, weighted):
  1. Cross-Module Consistency (30%): Consistent signal across platforms?
  2. Expression Predictiveness (25%): Does expression predict drug response?
  3. CAR-T Alignment (20%): B cell dependency for immune reset?
  4. Druggability (15%): Existing or repurposable drugs targeting this gene?
  5. Biomarker Novelty (10%): How novel is this biomarker?

Usage:
    python biomarker_discovery/discover.py              # Full analysis
    python biomarker_discovery/discover.py --top 15     # Top 15 biomarkers
    python biomarker_discovery/discover.py --export-html  # Generate report
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from med_research.exceptions import DataValidationError
from med_research.pipeline.knowledge_graph.config import load_relationships
import logging

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = Path(__file__).parent / "data"

logger = logging.getLogger(__name__)
last_coverage = None

# Module data dirs resolved from package layout (not CWD), so this works
# regardless of where the process is launched from.
_PIPELINE_ROOT = Path(__file__).parent.parent
_MODULE_DATA_DIRS = {
    "expression": _PIPELINE_ROOT / "gene_expression" / "data",
    "cart": _PIPELINE_ROOT / "car_t_predictor" / "data",
    "repurpose": _PIPELINE_ROOT / "drug_repurposing" / "data",
    "safety": _PIPELINE_ROOT / "adverse_events" / "data",
    "synergy": _PIPELINE_ROOT / "drug_synergy" / "data",
}


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Load All Module Results ──────────────────────────────────────────────


def _module_output_path(module: str, filename: str, disease_id: str = "sle") -> Path:
    """Resolve a module's output file for a disease.

    Prefers a per-disease file (expression_correlations_ra.json) when present;
    otherwise falls back to the shared file, which reflects the most recent
    pipeline run for whatever disease it was executed against.
    """
    data_dir = _MODULE_DATA_DIRS.get(module, DATA_DIR)
    per_disease = data_dir / f"{Path(filename).stem}_{disease_id}.json"
    if per_disease.exists():
        return per_disease
    return data_dir / filename


def load_all_modules(disease_id: str = "sle") -> dict:
    """Load results from all 5 scoring modules for a disease.

    Returns dict keyed by module name.
    """
    results = {}

    # Gene Expression Correlation
    try:
        data = load_json(_module_output_path("expression", "expression_correlations.json", disease_id))
        results["expression"] = {d["drug_id"]: d for d in data.get("drugs", [])}
    except (FileNotFoundError, KeyError):
        pass

    # CAR-T Response Predictor
    try:
        data = load_json(_module_output_path("cart", "car_t_scores.json", disease_id))
        results["cart"] = {g["gene_id"]: g for g in data.get("genes", [])}
    except (FileNotFoundError, KeyError):
        pass

    # Drug Repurposing candidates
    try:
        data = load_json(_module_output_path("repurpose", "candidates.json", disease_id))
        results["repurpose"] = data.get("repurposing_candidates", [])
    except (FileNotFoundError, KeyError):
        pass

    # Adverse Events
    try:
        data = load_json(_module_output_path("safety", "profiles.json", disease_id))
        results["safety"] = data
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        results["safety"] = {}

    # Drug Synergy
    try:
        data = load_json(_module_output_path("synergy", "synergy_results.json", disease_id))
        results["synergy"] = data.get("pairs", [])
    except (FileNotFoundError, KeyError):
        pass

    return results


# ── Gene → Module Score Mapping ─────────────────────────────────────────


_GENE_DRUG_TARGET_CACHE: dict = {}


def _build_gene_drug_target_map(disease_id: str = "sle") -> dict:
    """Build gene_id → [drug_id, ...] map from a disease's KG TARGETS relationships.

    Result is memoized per disease in a module-level cache since the
    relationships file doesn't change during a single process lifetime.
    """
    global _GENE_DRUG_TARGET_CACHE
    if disease_id in _GENE_DRUG_TARGET_CACHE:
        return _GENE_DRUG_TARGET_CACHE[disease_id]

    gene_to_drugs: dict = {}
    try:
        rel_data = load_relationships(disease_id)
        for rel in rel_data.get("relationships", []):
            if rel.get("type") == "TARGETS":
                gene_id = rel["target"]
                drug_id = rel["source"]
                if gene_id not in gene_to_drugs:
                    gene_to_drugs[gene_id] = []
                gene_to_drugs[gene_id].append(drug_id)
    except (DataValidationError, FileNotFoundError, KeyError, json.JSONDecodeError):
        pass

    _GENE_DRUG_TARGET_CACHE[disease_id] = gene_to_drugs
    return gene_to_drugs


def map_gene_to_modules(genes: dict, module_data: dict, disease_id: str = "sle") -> list:
    """Build a cross-module score matrix for each gene.

    For each gene, collects scores from all available modules and
    computes cross-module correlation metrics.
    """
    # Build gene → drug target mapping from KG relationships
    gene_to_drugs = _build_gene_drug_target_map(disease_id)

    matrix = []

    for gene_id, gene in genes.items():
        row = {
            "gene_id": gene_id,
            "gene_name": gene.get("name", gene_id),
            "category": gene.get("category", ""),
            "function": gene.get("function", "")[:150],
            "lupus_evidence": gene.get("lupus_evidence", "")[:150],
            "odds_ratio": gene.get("odds_ratio"),
        }

        # Expression correlation score — only for drugs that target this gene
        targeting_drugs = gene_to_drugs.get(gene_id, [])
        expr_scores = []
        if "expression" in module_data:
            for drug_id in targeting_drugs:
                if drug_id in module_data["expression"]:
                    expr_scores.append(module_data["expression"][drug_id].get("composite_score", 0))
        row["expression_avg"] = round(sum(expr_scores) / len(expr_scores), 2) if expr_scores else 0
        row["expression_max"] = round(max(expr_scores), 2) if expr_scores else 0
        row["targeting_drugs"] = len(targeting_drugs)

        # CAR-T score (gene-level)
        if "cart" in module_data and gene_id in module_data["cart"]:
            cart = module_data["cart"][gene_id]
            row["cart_score"] = cart.get("composite_score", 0)
            row["cart_tier"] = cart.get("tier", "")
        else:
            row["cart_score"] = 0
            row["cart_tier"] = ""

        # Drug Repurposing score (find candidates targeting this gene)
        rep_scores = []
        if "repurpose" in module_data:
            for c in module_data["repurpose"]:
                if c.get("gene_id") == gene_id:
                    rep_scores.append(c.get("composite_score", 0))
        row["repurpose_avg"] = round(sum(rep_scores) / len(rep_scores), 2) if rep_scores else 0
        row["repurpose_max"] = round(max(rep_scores), 2) if rep_scores else 0
        row["repurpose_count"] = len(rep_scores)

        # Safety score (gene → associated drugs)
        safety_scores = []
        if "safety" in module_data:
            for _drug_id, profile in module_data["safety"].items():
                if isinstance(profile, dict) and "composite_safety_score" in profile:
                    safety_scores.append(profile["composite_safety_score"])
        row["safety_avg"] = round(sum(safety_scores) / len(safety_scores), 2) if safety_scores else 5.0

        # Cross-module metrics
        module_scores = [v for v in [
            row["expression_max"],
            row["cart_score"],
            row["repurpose_max"],
        ] if v > 0]
        row["n_modules"] = len(module_scores)
        row["cross_module_mean"] = round(sum(module_scores) / len(module_scores), 2) if module_scores else 0

        # Consistency score: lower variance = more consistent signal
        if len(module_scores) >= 2:
            mean = sum(module_scores) / len(module_scores)
            variance = sum((s - mean) ** 2 for s in module_scores) / len(module_scores)
            row["consistency"] = round(max(0, 10 - variance * 2), 1)
        else:
            row["consistency"] = 5.0

        matrix.append(row)

    return matrix


# ── Scoring ─────────────────────────────────────────────────────────────


def score_biomarker(row: dict) -> dict:
    """Score a single gene as a biomarker across all treatment modalities."""
    consistency = row.get("consistency", 5.0)
    expression = row.get("expression_max", 0) * 0.8  # Scale to ~0-8
    cart = row.get("cart_score", 0) * 0.9
    druggability = min(10.0, row.get("targeting_drugs", 0) * 2.5)
    novelty = min(10.0, 10 - (row.get("targeting_drugs", 0) * 0.5)) if row.get("targeting_drugs", 0) < 5 else 2.0

    weights = {
        "cross_module_consistency": 0.30,
        "expression_predictiveness": 0.25,
        "cart_alignment": 0.20,
        "druggability": 0.15,
        "biomarker_novelty": 0.10,
    }

    composite = (
        consistency * weights["cross_module_consistency"]
        + expression * weights["expression_predictiveness"]
        + cart * weights["cart_alignment"]
        + druggability * weights["druggability"]
        + novelty * weights["biomarker_novelty"]
    )

    # Best treatment modality
    modalities = {
        "Drug Repurposing": row.get("repurpose_max", 0),
        "CAR-T Therapy": row.get("cart_score", 0),
        "Expression-Targeted": row.get("expression_max", 0),
    }
    best_modality = max(modalities, key=modalities.get)

    return {
        **row,
        "cross_module_consistency": round(consistency, 1),
        "expression_predictiveness": round(expression, 1),
        "cart_alignment": round(cart, 1),
        "druggability": round(druggability, 1),
        "biomarker_novelty": round(novelty, 1),
        "composite_score": round(composite, 2),
        "best_modality": best_modality,
        "best_modality_score": round(modalities[best_modality], 1),
        "tier": _assign_tier(composite),
    }


def _assign_tier(score: float) -> str:
    if score >= 8.0:
        return "🔴 Tier 1 — Strong Biomarker"
    elif score >= 6.5:
        return "🟠 Tier 2 — Promising Biomarker"
    elif score >= 5.0:
        return "🟡 Tier 3 — Emergent Biomarker"
    return "🟢 Tier 4 — Investigational"


def compute_biomarker_matrix(progress_callback=None, disease_id: str = "sle", save: bool = True) -> list:
    """Full pipeline: load modules, map genes, score biomarkers.

    Args:
        progress_callback: Optional callable(percent, message) for progress.
        disease_id: Disease whose KG genes and module outputs are used.
        save: When False, compute in memory without writing the shared
            biomarker_matrix.json (used by the comparative cross-disease run
            so per-disease scoring doesn't clobber the last-run results).
    """
    cb = progress_callback or (lambda p, m: None)

    from med_research.diseases.coverage import module_coverage

    global last_coverage
    coverage = module_coverage(disease_id, "biomarkers", ("genes",))
    last_coverage = coverage
    if not coverage.is_runnable:
        cb(100, f"Biomarker analysis blocked: {', '.join(coverage.missing_inputs)}")
        return []

    cb(0, "Loading knowledge graph genes...")
    from med_research.pipeline.knowledge_graph.builder import build_graph
    G = build_graph(disease_id)
    genes = {}
    for node, data in G.nodes(data=True):
        if data.get("type") == "gene":
            genes[node] = data

    cb(15, f"Loaded {len(genes)} genes")

    cb(20, "Loading module results...")
    module_data = load_all_modules(disease_id)

    cb(40, "Building cross-module matrix...")
    matrix = map_gene_to_modules(genes, module_data, disease_id)

    cb(60, f"Scoring {len(matrix)} biomarkers...")
    results = [score_biomarker(row) for row in matrix]
    results.sort(key=lambda x: x["composite_score"], reverse=True)

    if save:
        cb(95, "Saving results...")
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        output_path = DATA_DIR / "biomarker_matrix.json"
        output_path.write_text(json.dumps({
            "biomarkers": results,
            "total_genes": len(results),
        }, indent=2), encoding="utf-8")
        cb(100, f"Results saved to {output_path}")
    else:
        cb(100, "Biomarker scoring complete (in-memory)")
    return results


# ── CLI ──────────────────────────────────────────────────────────────────


def analyze(results: list):
    """Print summary."""
    logger.info("\n" + "=" * 75)
    logger.info("🧬 BIOMARKER DISCOVERY — Cross-Module Integration")
    logger.info("=" * 75)

    scores = [r["composite_score"] for r in results]
    logger.info(f"\n  {len(results)} genes analyzed across 5 platforms")
    logger.info(f"  Score range: {min(scores):.2f} - {max(scores):.2f}")
    logger.info(f"  Mean score: {sum(scores)/len(scores):.2f}")

    tier_counts = {}
    for r in results:
        tier_counts[r["tier"]] = tier_counts.get(r["tier"], 0) + 1
    logger.info("\n  Distribution by tier:")
    for tier in ["🔴 Tier 1 — Strong Biomarker", "🟠 Tier 2 — Promising Biomarker",
                  "🟡 Tier 3 — Emergent Biomarker", "🟢 Tier 4 — Investigational"]:
        count = tier_counts.get(tier, 0)
        label = tier.split("—")[0].strip()
        logger.info(f"    {label}: {count} biomarkers")


def print_top_biomarkers(results: list, top_n: int = 15):
    """Print top biomarkers."""
    logger.info("\n" + "=" * 75)
    logger.info(f"🎯 TOP {top_n} BIOMARKER CANDIDATES")
    logger.info("=" * 75)

    for i, r in enumerate(results[:top_n], 1):
        logger.info(f"\n  #{i} | {r['tier']}")
        logger.info("  " + "─" * 50)
        logger.info(f"  🧬 Gene:      {r['gene_name']} ({r['gene_id']})")
        logger.info(f"  📂 Category:   {r.get('category', '')}")
        logger.info(f"  ⭐ Score:      {r['composite_score']:.2f}/10")
        logger.info(f"     ├─ Cross-Module Consistency: {r['cross_module_consistency']}/10")
        logger.info(f"     ├─ Expression Predictiveness: {r['expression_predictiveness']}/10")
        logger.info(f"     ├─ CAR-T Alignment:          {r['cart_alignment']}/10")
        logger.info(f"     ├─ Druggability:             {r['druggability']}/10")
        logger.info(f"     └─ Biomarker Novelty:        {r['biomarker_novelty']}/10")
        logger.info(f"  💊 Best Modality: {r['best_modality']} ({r['best_modality_score']})")


def main():
    parser = argparse.ArgumentParser(
        description="Biomarker Discovery — Cross-module integration for lupus therapy biomarkers"
    )
    parser.add_argument("--top", type=int, default=15, help="Number of top biomarkers to display")
    parser.add_argument("--disease", "-d", default="sle", help="Disease ID (default: sle)")
    parser.add_argument("--export-html", action="store_true", help="Generate HTML report")
    args = parser.parse_args()

    results = compute_biomarker_matrix(disease_id=args.disease)
    analyze(results)
    print_top_biomarkers(results, args.top)

    if args.export_html:
        from med_research.pipeline.biomarker_discovery.report import generate_html_report
        generate_html_report(results, disease_id=args.disease)
        logger.info("\n✅ HTML report generated: biomarker_discovery/report.html")

    return results


if __name__ == "__main__":
    main()
