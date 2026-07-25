"""
CAR-T Response Predictor

Scores all 35 lupus-associated genes for CD19 CAR-T cell therapy suitability.
Identifies which genes/pathways are most B-cell-dependent and therefore most
likely to respond to a CD19-directed CAR-T "immune reset".

Scoring Dimensions (each 0-10, weighted):
  1. B Cell Dependency (35%): How central is the gene to B cell biology?
  2. Autoantibody Association (25%): How strongly linked to pathogenic autoantibodies?
  3. Plasma Cell Relevance (20%): Is the gene critical for plasma cell survival?
  4. CD19 Targeting (15%): Does CD19 CAR-T directly impact this pathway?
  5. Clinical Evidence (5%): Existing CAR-T data involving this pathway?

Usage:
    python car_t_predictor/predictor.py              # Full analysis
    python car_t_predictor/predictor.py --top 15     # Top 15 genes
    python car_t_predictor/predictor.py --export-html  # Generate report
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = Path(__file__).parent / "data"

from med_research.pipeline.knowledge_graph.config import load_genes as config_load_genes


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_genes() -> dict:
    """Load all genes indexed by gene ID."""
    data = config_load_genes()
    return {g["id"]: g for g in data["genes"]}


# ── Gene Categorization for CAR-T Scoring ────────────────────────────────

# How central is this gene to B cell biology? (0-10)
B_CELL_DEPENDENCY = {
    "CD20": 10.0, "MS4A1": 10.0, "CD19": 10.0,
    "BLK": 9.5, "BANK1": 9.0, "BTK": 9.5,
    "BAFF": 9.0, "TNFSF13B": 9.0, "PRDM1": 9.0,
    "IKZF1": 8.5, "IKZF3": 8.5,
    "PTPN22": 8.0, "UBE2L3": 7.5,
    "CD40L": 7.0, "CD40LG": 7.0, "TNFSF4": 6.5,
    "HLA-DRB1": 6.0, "IRF5": 5.5, "STAT4": 5.5,
    "TLR7": 5.0, "TLR9": 5.0, "MYD88": 4.5,
    "IRAK4": 4.5, "IRF7": 4.0, "TYK2": 4.0,
    "JAK1": 4.0, "TNFAIP3": 5.5, "TNIP1": 5.0,
    "FCGR2A": 3.0, "FCGR3A": 3.0, "ITGAM": 3.0,
    "ELMO1": 2.0, "C1QA": 1.0, "C2": 1.0, "C4A": 1.0,
    "ATG5": 3.0, "IMPDH": 6.0, "Calcineurin": 4.0,
    "Glucocorticoid Receptor": 5.0, "IFNAR1": 4.5,
}

# How strongly associated with pathogenic autoantibodies (anti-dsDNA, ANA)?
AUTOANTIBODY_ASSOCIATION = {
    "BAFF": 10.0, "TNFSF13B": 10.0, "PRDM1": 9.5,
    "CD40L": 9.0, "CD40LG": 9.0, "IKZF3": 9.0,
    "UBE2L3": 8.5, "TLR7": 8.5, "TLR9": 8.0,
    "BLK": 8.0, "BANK1": 8.0, "BTK": 8.0,
    "IKZF1": 8.0, "IRF5": 7.5, "HLA-DRB1": 7.5,
    "CD20": 7.0, "CD19": 7.0, "MS4A1": 7.0,
    "MYD88": 7.0, "IRAK4": 6.5, "TNFSF4": 7.0,
    "PTPN22": 6.5, "STAT4": 6.0, "TNFAIP3": 6.0,
    "TNIP1": 5.5, "TYK2": 5.5, "JAK1": 5.0,
    "IRF7": 5.0, "FCGR2A": 4.0, "FCGR3A": 4.0,
    "ITGAM": 3.5, "C1QA": 3.0, "C2": 3.0, "C4A": 3.0,
    "ELMO1": 2.0, "ATG5": 3.5, "IMPDH": 5.5,
    "Calcineurin": 4.0, "Glucocorticoid Receptor": 4.0,
    "IFNAR1": 5.0,
}

# Is this gene critical for long-lived plasma cell survival?
PLASMA_CELL_RELEVANCE = {
    "PRDM1": 10.0, "IKZF3": 10.0, "IKZF1": 9.5,
    "UBE2L3": 9.0, "BAFF": 9.0, "TNFSF13B": 9.0,
    "CD19": 8.5, "CD20": 8.0, "MS4A1": 8.0,
    "BTK": 7.5, "BLK": 7.0, "CD40L": 7.0,
    "CD40LG": 7.0, "BANK1": 6.5, "TNFSF4": 6.0,
    "HLA-DRB1": 5.5, "TLR7": 5.0, "TLR9": 5.0,
    "MYD88": 4.5, "IRAK4": 4.0, "PTPN22": 5.5,
    "IMPDH": 5.0, "STAT4": 4.5, "IRF5": 4.0,
    "IRF7": 3.5, "TYK2": 3.0, "JAK1": 3.0,
    "TNFAIP3": 4.5, "TNIP1": 4.0,
    "FCGR2A": 2.0, "FCGR3A": 2.0, "ITGAM": 2.0,
    "ELMO1": 1.0, "C1QA": 1.0, "C2": 1.0, "C4A": 1.0,
    "ATG5": 2.5, "Calcineurin": 3.5,
    "Glucocorticoid Receptor": 4.0, "IFNAR1": 3.5,
}

# Does CD19 CAR-T directly affect this pathway?
CD19_TARGETING = {
    "CD19": 10.0, "CD20": 9.5, "MS4A1": 9.5,
    "BLK": 9.0, "BTK": 9.0, "BANK1": 8.5,
    "BAFF": 8.5, "TNFSF13B": 8.5, "PRDM1": 9.0,
    "IKZF1": 8.5, "IKZF3": 8.5, "PTPN22": 8.0,
    "UBE2L3": 8.0, "CD40L": 7.5, "CD40LG": 7.5,
    "TNFSF4": 6.5, "HLA-DRB1": 6.0, "IMPDH": 6.0,
    "TLR7": 5.0, "TLR9": 5.0, "MYD88": 4.5,
    "IRAK4": 4.0, "IRF5": 5.5, "STAT4": 5.0,
    "IRF7": 4.0, "TYK2": 4.0, "JAK1": 4.0,
    "TNFAIP3": 5.5, "TNIP1": 5.0,
    "FCGR2A": 3.0, "FCGR3A": 3.0, "ITGAM": 3.0,
    "ELMO1": 2.0, "C1QA": 2.0, "C2": 2.0, "C4A": 2.0,
    "ATG5": 3.5, "Calcineurin": 4.0,
    "Glucocorticoid Receptor": 5.0, "IFNAR1": 5.5,
}

# Existing published evidence for CAR-T or deep B cell depletion in this pathway
CAR_T_EVIDENCE = {
    "CD19": 10.0, "CD20": 9.5, "MS4A1": 9.5,
    "PRDM1": 8.0, "BLK": 7.5, "BTK": 7.5,
    "BAFF": 7.0, "TNFSF13B": 7.0, "IKZF3": 7.0,
    "IKZF1": 6.5, "BANK1": 6.0, "PTPN22": 6.0,
    "UBE2L3": 5.5, "CD40L": 5.5, "CD40LG": 5.5,
    "HLA-DRB1": 5.0, "IMPDH": 5.0, "TNFSF4": 4.5,
    "TLR7": 4.0, "TLR9": 4.0, "IRF5": 3.5,
    "STAT4": 3.5, "IRF7": 3.0, "TYK2": 3.0,
    "JAK1": 3.0, "MYD88": 3.0, "IRAK4": 2.5,
    "TNFAIP3": 3.5, "TNIP1": 3.0,
    "FCGR2A": 2.0, "FCGR3A": 2.0, "ITGAM": 2.0,
    "ELMO1": 1.0, "C1QA": 1.0, "C2": 1.0, "C4A": 1.0,
    "ATG5": 2.0, "Calcineurin": 3.0,
    "Glucocorticoid Receptor": 4.0, "IFNAR1": 4.5,
}


def score_gene(gene_id: str, gene: dict) -> dict:
    """Score a single gene for CAR-T therapy suitability.

    Returns dict with individual scores and composite score.
    """
    b_cell = B_CELL_DEPENDENCY.get(gene_id, 3.0)
    auto_ab = AUTOANTIBODY_ASSOCIATION.get(gene_id, 3.0)
    plasma = PLASMA_CELL_RELEVANCE.get(gene_id, 3.0)
    cd19 = CD19_TARGETING.get(gene_id, 3.0)
    evidence = CAR_T_EVIDENCE.get(gene_id, 2.0)

    weights = {
        "b_cell_dependency": 0.35,
        "autoantibody_association": 0.25,
        "plasma_cell_relevance": 0.20,
        "cd19_targeting": 0.15,
        "clinical_evidence": 0.05,
    }

    composite = (
        b_cell * weights["b_cell_dependency"]
        + auto_ab * weights["autoantibody_association"]
        + plasma * weights["plasma_cell_relevance"]
        + cd19 * weights["cd19_targeting"]
        + evidence * weights["clinical_evidence"]
    )

    return {
        "gene_id": gene_id,
        "gene_name": gene.get("name", gene_id),
        "category": gene.get("category", ""),
        "function": gene.get("function", "")[:200],
        "lupus_evidence": gene.get("lupus_evidence", "")[:200],
        "odds_ratio": gene.get("odds_ratio"),
        "b_cell_dependency": round(b_cell, 1),
        "autoantibody_association": round(auto_ab, 1),
        "plasma_cell_relevance": round(plasma, 1),
        "cd19_targeting": round(cd19, 1),
        "clinical_evidence": round(evidence, 1),
        "composite_score": round(composite, 2),
        "tier": _assign_tier(composite),
        "recommendation": _recommendation(composite),
    }


def _assign_tier(score: float) -> str:
    if score >= 8.0:
        return "🔴 Tier 1 — Strong CAR-T Candidate"
    elif score >= 7.0:
        return "🟠 Tier 2 — Good CAR-T Candidate"
    elif score >= 5.0:
        return "🟡 Tier 3 — Possible CAR-T Benefit"
    return "🟢 Tier 4 — Limited CAR-T Benefit"


def _recommendation(score: float) -> str:
    if score >= 8.0:
        return "High likelihood of response to CD19 CAR-T. B-cell-dependent pathway with strong plasma cell involvement."
    elif score >= 7.0:
        return "Good candidate. CAR-T should address core pathway dysfunction. Consider combination with targeted therapy."
    elif score >= 5.0:
        return "May benefit from CAR-T indirectly through B cell depletion. Monitor for non-B-cell disease activity."
    return "Limited direct CAR-T benefit. Pathway not primarily B-cell-driven. Consider alternative therapies."


def compute_all_scores(progress_callback=None) -> list:
    """Score all 35 lupus genes for CAR-T suitability.

    Returns list of scored genes sorted by composite score descending.
    """
    cb = progress_callback or (lambda p, m: None)

    cb(0, "Loading gene database...")
    genes = load_genes()

    cb(10, f"Scoring {len(genes)} genes for CAR-T suitability...")
    results = []
    for i, (gene_id, gene) in enumerate(genes.items()):
        if i % 5 == 0:
            cb(10 + int(i / len(genes) * 75), f"Scoring {gene_id}...")
        results.append(score_gene(gene_id, gene))

    results.sort(key=lambda x: x["composite_score"], reverse=True)

    cb(95, "Saving results...")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DATA_DIR / "car_t_scores.json"
    output_path.write_text(json.dumps({
        "genes": results,
        "total_genes": len(results),
    }, indent=2), encoding="utf-8")

    cb(100, f"Results saved to {output_path}")
    return results


# ── CLI ──────────────────────────────────────────────────────────────────


def analyze(results: list):
    """Print statistical summary."""
    print("\n" + "=" * 75)
    print("🔬 CAR-T RESPONSE PREDICTOR — Gene-Level Analysis")
    print("=" * 75)

    scores = [r["composite_score"] for r in results]
    print(f"\n  {len(results)} genes scored for CD19 CAR-T suitability")
    print(f"  Score range: {min(scores):.2f} - {max(scores):.2f}")
    print(f"  Mean score: {sum(scores)/len(scores):.2f}")

    tier_counts = {}
    for r in results:
        tier_counts[r["tier"]] = tier_counts.get(r["tier"], 0) + 1
    print("\n  Distribution by tier:")
    for tier in ["🔴 Tier 1 — Strong CAR-T Candidate", "🟠 Tier 2 — Good CAR-T Candidate",
                  "🟡 Tier 3 — Possible CAR-T Benefit", "🟢 Tier 4 — Limited CAR-T Benefit"]:
        count = tier_counts.get(tier, 0)
        label = tier.split("—")[0].strip()
        print(f"    {label}: {count} genes")


def print_top_genes(results: list, top_n: int = 15):
    """Print the top N genes by CAR-T suitability."""
    print("\n" + "=" * 75)
    print(f"🎯 TOP {top_n} GENES FOR CD19 CAR-T SUITABILITY")
    print("=" * 75)

    for i, r in enumerate(results[:top_n], 1):
        print(f"\n  #{i} | {r['tier']}")
        print("  " + "─" * 50)
        print(f"  🧬 Gene:     {r['gene_name']}")
        print(f"  📂 Category:  {r.get('category', '')}")
        print(f"  ⭐ Score:     {r['composite_score']:.2f}/10")
        print(f"     ├─ B Cell Dependency:     {r['b_cell_dependency']}/10")
        print(f"     ├─ Autoantibody Assoc:    {r['autoantibody_association']}/10")
        print(f"     ├─ Plasma Cell Relevance: {r['plasma_cell_relevance']}/10")
        print(f"     ├─ CD19 Targeting:        {r['cd19_targeting']}/10")
        print(f"     └─ Clinical Evidence:     {r['clinical_evidence']}/10")
        print(f"  💡 {r['recommendation']}")


def main():
    parser = argparse.ArgumentParser(
        description="CAR-T Response Predictor — Score lupus genes for CD19 CAR-T suitability"
    )
    parser.add_argument("--top", type=int, default=15, help="Number of top genes to display")
    parser.add_argument("--export-html", action="store_true", help="Generate HTML report")
    args = parser.parse_args()

    results = compute_all_scores()
    analyze(results)
    print_top_genes(results, args.top)

    if args.export_html:
        from med_research.pipeline.car_t_predictor.report import generate_html_report
        generate_html_report(results)
        print("\n✅ HTML report generated: car_t_predictor/report.html")

    return results


if __name__ == "__main__":
    main()
