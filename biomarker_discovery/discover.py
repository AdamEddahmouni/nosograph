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

from knowledge_graph.config import load_relationships

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = Path(__file__).parent / "data"


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Load All Module Results ──────────────────────────────────────────────


def load_all_modules() -> dict:
    """Load results from all 5 scoring modules. Returns dict keyed by module name."""
    results = {}

    # Gene Expression Correlation
    try:
        data = load_json(Path("gene_expression/data/expression_correlations.json"))
        results["expression"] = {d["drug_id"]: d for d in data.get("drugs", [])}
    except (FileNotFoundError, KeyError):
        pass

    # CAR-T Response Predictor
    try:
        data = load_json(Path("car_t_predictor/data/car_t_scores.json"))
        results["cart"] = {g["gene_id"]: g for g in data.get("genes", [])}
    except (FileNotFoundError, KeyError):
        pass

    # Drug Repurposing candidates
    try:
        data = load_json(Path("drug_repurposing/data/candidates.json"))
        results["repurpose"] = data.get("repurposing_candidates", [])
    except (FileNotFoundError, KeyError):
        pass

    # Adverse Events
    try:
        data = load_json(Path("adverse_events/data/profiles.json"))
        results["safety"] = data
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        results["safety"] = {}

    # Drug Synergy
    try:
        data = load_json(Path("drug_synergy/data/synergy_results.json"))
        results["synergy"] = data.get("pairs", [])
    except (FileNotFoundError, KeyError):
        pass

    return results


# ── Gene → Module Score Mapping ─────────────────────────────────────────


_GENE_DRUG_TARGET_CACHE: dict | None = None


def _build_gene_drug_target_map() -> dict:
    """Build gene_id → [drug_id, ...] map from KG TARGETS relationships.

    Result is memoized in a module-level cache since the relationships
    file doesn't change during a single process lifetime.
    """
    global _GENE_DRUG_TARGET_CACHE
    if _GENE_DRUG_TARGET_CACHE is not None:
        return _GENE_DRUG_TARGET_CACHE

    gene_to_drugs: dict = {}
    try:
        rel_data = load_relationships()
        for rel in rel_data.get("relationships", []):
            if rel.get("type") == "TARGETS":
                gene_id = rel["target"]
                drug_id = rel["source"]
                if gene_id not in gene_to_drugs:
                    gene_to_drugs[gene_id] = []
                gene_to_drugs[gene_id].append(drug_id)
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        pass

    _GENE_DRUG_TARGET_CACHE = gene_to_drugs
    return gene_to_drugs


def map_gene_to_modules(genes: dict, module_data: dict) -> list:
    """Build a cross-module score matrix for each gene.

    For each gene, collects scores from all available modules and
    computes cross-module correlation metrics.
    """
    # Build gene → drug target mapping from KG relationships
    gene_to_drugs = _build_gene_drug_target_map()

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


def compute_biomarker_matrix(progress_callback=None) -> list:
    """Full pipeline: load modules, map genes, score biomarkers."""
    cb = progress_callback or (lambda p, m: None)

    cb(0, "Loading knowledge graph genes...")
    from knowledge_graph.build_graph import build_graph
    G = build_graph()
    genes = {}
    for node, data in G.nodes(data=True):
        if data.get("type") == "gene":
            genes[node] = data

    cb(15, f"Loaded {len(genes)} genes")

    cb(20, "Loading module results...")
    module_data = load_all_modules()

    cb(40, "Building cross-module matrix...")
    matrix = map_gene_to_modules(genes, module_data)

    cb(60, f"Scoring {len(matrix)} biomarkers...")
    results = [score_biomarker(row) for row in matrix]
    results.sort(key=lambda x: x["composite_score"], reverse=True)

    cb(95, "Saving results...")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DATA_DIR / "biomarker_matrix.json"
    output_path.write_text(json.dumps({
        "biomarkers": results,
        "total_genes": len(results),
    }, indent=2), encoding="utf-8")

    cb(100, f"Results saved to {output_path}")
    return results


# ── CLI ──────────────────────────────────────────────────────────────────


def analyze(results: list):
    """Print summary."""
    print("\n" + "=" * 75)
    print("🧬 BIOMARKER DISCOVERY — Cross-Module Integration")
    print("=" * 75)

    scores = [r["composite_score"] for r in results]
    print(f"\n  {len(results)} genes analyzed across 5 platforms")
    print(f"  Score range: {min(scores):.2f} - {max(scores):.2f}")
    print(f"  Mean score: {sum(scores)/len(scores):.2f}")

    tier_counts = {}
    for r in results:
        tier_counts[r["tier"]] = tier_counts.get(r["tier"], 0) + 1
    print("\n  Distribution by tier:")
    for tier in ["🔴 Tier 1 — Strong Biomarker", "🟠 Tier 2 — Promising Biomarker",
                  "🟡 Tier 3 — Emergent Biomarker", "🟢 Tier 4 — Investigational"]:
        count = tier_counts.get(tier, 0)
        label = tier.split("—")[0].strip()
        print(f"    {label}: {count} biomarkers")


def print_top_biomarkers(results: list, top_n: int = 15):
    """Print top biomarkers."""
    print("\n" + "=" * 75)
    print(f"🎯 TOP {top_n} BIOMARKER CANDIDATES")
    print("=" * 75)

    for i, r in enumerate(results[:top_n], 1):
        print(f"\n  #{i} | {r['tier']}")
        print("  " + "─" * 50)
        print(f"  🧬 Gene:      {r['gene_name']} ({r['gene_id']})")
        print(f"  📂 Category:   {r.get('category', '')}")
        print(f"  ⭐ Score:      {r['composite_score']:.2f}/10")
        print(f"     ├─ Cross-Module Consistency: {r['cross_module_consistency']}/10")
        print(f"     ├─ Expression Predictiveness: {r['expression_predictiveness']}/10")
        print(f"     ├─ CAR-T Alignment:          {r['cart_alignment']}/10")
        print(f"     ├─ Druggability:             {r['druggability']}/10")
        print(f"     └─ Biomarker Novelty:        {r['biomarker_novelty']}/10")
        print(f"  💊 Best Modality: {r['best_modality']} ({r['best_modality_score']})")


def main():
    parser = argparse.ArgumentParser(
        description="Biomarker Discovery — Cross-module integration for lupus therapy biomarkers"
    )
    parser.add_argument("--top", type=int, default=15, help="Number of top biomarkers to display")
    parser.add_argument("--export-html", action="store_true", help="Generate HTML report")
    args = parser.parse_args()

    results = compute_biomarker_matrix()
    analyze(results)
    print_top_biomarkers(results, args.top)

    if args.export_html:
        from biomarker_discovery.report import generate_html_report
        generate_html_report(results)
        print("\n✅ HTML report generated: biomarker_discovery/report.html")

    return results


if __name__ == "__main__":
    main()
