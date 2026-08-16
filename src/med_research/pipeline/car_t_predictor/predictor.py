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
import logging
from pathlib import Path
from typing import cast

from med_research.cache import disease_output_path, write_json_atomic
from med_research.pipeline.knowledge_graph.config import load_genes as config_load_genes
from med_research.pipeline.progress import StandardProgress, _tick, cli_progress
from med_research.pipeline.results import CarTGeneScore

DATA_DIR = Path(__file__).parent / "data"

logger = logging.getLogger(__name__)
last_coverage = None


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return cast(dict, json.load(f))


def load_genes(disease_id: str = "sle") -> dict:
    """Load all genes for a disease indexed by gene ID."""
    data = config_load_genes(disease_id)
    return {g["id"]: g for g in data["genes"]}


# ── Gene Categorization for CAR-T Scoring ────────────────────────────────

# How central is this gene to B cell biology? (0-10)
B_CELL_DEPENDENCY = {
    "CD20": 10.0,
    "MS4A1": 10.0,
    "CD19": 10.0,
    "BLK": 9.5,
    "BANK1": 9.0,
    "BTK": 9.5,
    "BAFF": 9.0,
    "TNFSF13B": 9.0,
    "PRDM1": 9.0,
    "IKZF1": 8.5,
    "IKZF3": 8.5,
    "PTPN22": 8.0,
    "UBE2L3": 7.5,
    "CD40L": 7.0,
    "CD40LG": 7.0,
    "TNFSF4": 6.5,
    "HLA-DRB1": 6.0,
    "IRF5": 5.5,
    "STAT4": 5.5,
    "TLR7": 5.0,
    "TLR9": 5.0,
    "MYD88": 4.5,
    "IRAK4": 4.5,
    "IRF7": 4.0,
    "TYK2": 4.0,
    "JAK1": 4.0,
    "TNFAIP3": 5.5,
    "TNIP1": 5.0,
    "FCGR2A": 3.0,
    "FCGR3A": 3.0,
    "ITGAM": 3.0,
    "ELMO1": 2.0,
    "C1QA": 1.0,
    "C2": 1.0,
    "C4A": 1.0,
    "ATG5": 3.0,
    "IMPDH": 6.0,
    "Calcineurin": 4.0,
    "Glucocorticoid Receptor": 5.0,
    "IFNAR1": 4.5,
}

# How strongly associated with pathogenic autoantibodies (anti-dsDNA, ANA)?
AUTOANTIBODY_ASSOCIATION = {
    "BAFF": 10.0,
    "TNFSF13B": 10.0,
    "PRDM1": 9.5,
    "CD40L": 9.0,
    "CD40LG": 9.0,
    "IKZF3": 9.0,
    "UBE2L3": 8.5,
    "TLR7": 8.5,
    "TLR9": 8.0,
    "BLK": 8.0,
    "BANK1": 8.0,
    "BTK": 8.0,
    "IKZF1": 8.0,
    "IRF5": 7.5,
    "HLA-DRB1": 7.5,
    "CD20": 7.0,
    "CD19": 7.0,
    "MS4A1": 7.0,
    "MYD88": 7.0,
    "IRAK4": 6.5,
    "TNFSF4": 7.0,
    "PTPN22": 6.5,
    "STAT4": 6.0,
    "TNFAIP3": 6.0,
    "TNIP1": 5.5,
    "TYK2": 5.5,
    "JAK1": 5.0,
    "IRF7": 5.0,
    "FCGR2A": 4.0,
    "FCGR3A": 4.0,
    "ITGAM": 3.5,
    "C1QA": 3.0,
    "C2": 3.0,
    "C4A": 3.0,
    "ELMO1": 2.0,
    "ATG5": 3.5,
    "IMPDH": 5.5,
    "Calcineurin": 4.0,
    "Glucocorticoid Receptor": 4.0,
    "IFNAR1": 5.0,
}

# Is this gene critical for long-lived plasma cell survival?
PLASMA_CELL_RELEVANCE = {
    "PRDM1": 10.0,
    "IKZF3": 10.0,
    "IKZF1": 9.5,
    "UBE2L3": 9.0,
    "BAFF": 9.0,
    "TNFSF13B": 9.0,
    "CD19": 8.5,
    "CD20": 8.0,
    "MS4A1": 8.0,
    "BTK": 7.5,
    "BLK": 7.0,
    "CD40L": 7.0,
    "CD40LG": 7.0,
    "BANK1": 6.5,
    "TNFSF4": 6.0,
    "HLA-DRB1": 5.5,
    "TLR7": 5.0,
    "TLR9": 5.0,
    "MYD88": 4.5,
    "IRAK4": 4.0,
    "PTPN22": 5.5,
    "IMPDH": 5.0,
    "STAT4": 4.5,
    "IRF5": 4.0,
    "IRF7": 3.5,
    "TYK2": 3.0,
    "JAK1": 3.0,
    "TNFAIP3": 4.5,
    "TNIP1": 4.0,
    "FCGR2A": 2.0,
    "FCGR3A": 2.0,
    "ITGAM": 2.0,
    "ELMO1": 1.0,
    "C1QA": 1.0,
    "C2": 1.0,
    "C4A": 1.0,
    "ATG5": 2.5,
    "Calcineurin": 3.5,
    "Glucocorticoid Receptor": 4.0,
    "IFNAR1": 3.5,
}

# Does CD19 CAR-T directly affect this pathway?
CD19_TARGETING = {
    "CD19": 10.0,
    "CD20": 9.5,
    "MS4A1": 9.5,
    "BLK": 9.0,
    "BTK": 9.0,
    "BANK1": 8.5,
    "BAFF": 8.5,
    "TNFSF13B": 8.5,
    "PRDM1": 9.0,
    "IKZF1": 8.5,
    "IKZF3": 8.5,
    "PTPN22": 8.0,
    "UBE2L3": 8.0,
    "CD40L": 7.5,
    "CD40LG": 7.5,
    "TNFSF4": 6.5,
    "HLA-DRB1": 6.0,
    "IMPDH": 6.0,
    "TLR7": 5.0,
    "TLR9": 5.0,
    "MYD88": 4.5,
    "IRAK4": 4.0,
    "IRF5": 5.5,
    "STAT4": 5.0,
    "IRF7": 4.0,
    "TYK2": 4.0,
    "JAK1": 4.0,
    "TNFAIP3": 5.5,
    "TNIP1": 5.0,
    "FCGR2A": 3.0,
    "FCGR3A": 3.0,
    "ITGAM": 3.0,
    "ELMO1": 2.0,
    "C1QA": 2.0,
    "C2": 2.0,
    "C4A": 2.0,
    "ATG5": 3.5,
    "Calcineurin": 4.0,
    "Glucocorticoid Receptor": 5.0,
    "IFNAR1": 5.5,
}

# Existing published evidence for CAR-T or deep B cell depletion in this pathway
CAR_T_EVIDENCE = {
    "CD19": 10.0,
    "CD20": 9.5,
    "MS4A1": 9.5,
    "PRDM1": 8.0,
    "BLK": 7.5,
    "BTK": 7.5,
    "BAFF": 7.0,
    "TNFSF13B": 7.0,
    "IKZF3": 7.0,
    "IKZF1": 6.5,
    "BANK1": 6.0,
    "PTPN22": 6.0,
    "UBE2L3": 5.5,
    "CD40L": 5.5,
    "CD40LG": 5.5,
    "HLA-DRB1": 5.0,
    "IMPDH": 5.0,
    "TNFSF4": 4.5,
    "TLR7": 4.0,
    "TLR9": 4.0,
    "IRF5": 3.5,
    "STAT4": 3.5,
    "IRF7": 3.0,
    "TYK2": 3.0,
    "JAK1": 3.0,
    "MYD88": 3.0,
    "IRAK4": 2.5,
    "TNFAIP3": 3.5,
    "TNIP1": 3.0,
    "FCGR2A": 2.0,
    "FCGR3A": 2.0,
    "ITGAM": 2.0,
    "ELMO1": 1.0,
    "C1QA": 1.0,
    "C2": 1.0,
    "C4A": 1.0,
    "ATG5": 2.0,
    "Calcineurin": 3.0,
    "Glucocorticoid Receptor": 4.0,
    "IFNAR1": 4.5,
}


# Dimension keys used by dimension-keyed disease configs (e.g. SLE).
_DIMENSION_KEYS = {
    "b_cell": "B_CELL_DEPENDENCY",
    "auto_ab": "AUTOANTIBODY_ASSOCIATION",
    "plasma": "PLASMA_CELL_RELEVANCE",
    "cd19": "CD19_TARGETING",
    "evidence": "CAR_T_EVIDENCE",
}


def _category_dimension_weights(category: str) -> dict:
    """Map a category label to per-dimension weights (0-1) by keyword semantics.

    Used for category-keyed disease configs (e.g. RA: {"B Cell Signaling":
    {"BLK": 9.0, ...}}). A gene's dimension score = its category score scaled
    by the category's B-cell relevance, so non-SLE rubrics actually differ.
    Returns a dict keyed by the _DIMENSION_KEYS dimensions, so callers can
    zip safely without positional-order coupling.
    """
    c = (category or "").lower()
    weights = {"b_cell": 0.4, "auto_ab": 0.4, "plasma": 0.3, "cd19": 0.4, "evidence": 0.4}

    if any(
        k in c
        for k in (
            "b cell",
            "b-cell",
            "germinal",
            "plasma",
            "baff",
            "tfh",
            "bcr",
            "b lymphocyte",
            "antibody",
        )
    ):
        weights["b_cell"] = 0.9
        weights["cd19"] = 0.85
        weights["evidence"] = 0.7
    if any(
        k in c
        for k in ("autoantibody", "antibody", "humoral", "immunoglobulin", "igg", "igm", "dsdna")
    ):
        weights["auto_ab"] = 0.9
    if any(
        k in c for k in ("plasma cell", "plasma-cell", "long-lived", "germinal center", "survival")
    ):
        weights["plasma"] = 0.9
    if (
        any(
            k in c
            for k in (
                "t cell",
                "t-cell",
                "cytokine",
                "th1",
                "th17",
                "innate",
                "macrophage",
                "neutrophil",
                "epithelial",
                "barrier",
                "microbiome",
            )
        )
        and weights["b_cell"] < 0.8
    ):
        weights["b_cell"] = 0.2

    return weights


def load_config_scoring(disease_id: str = "sle") -> dict:
    """Load per-disease CAR-T scoring dicts from the disease config.

    Returns a dict of the five scoring sub-dicts (B_CELL_DEPENDENCY,
    AUTOANTIBODY_ASSOCIATION, PLASMA_CELL_RELEVANCE, CD19_TARGETING,
    CAR_T_EVIDENCE), with the disease config's values merged over the
    hardcoded defaults.

    Supports both config shapes:
      * dimension-keyed (SLE): {"B_CELL_DEPENDENCY": {...}, ...}
      * category-keyed (RA, MS, IBD, SS, SSc, T1D): {"B Cell Signaling":
        {"BLK": 9.0, ...}, ...} — dimension scores are derived from each
        category's B-cell semantics and the gene's category score.
    An empty disease configuration produces an empty override; callers must
    enforce module coverage before using this compatibility helper.
    """
    from med_research.diseases.base import Disease

    try:
        config = Disease(disease_id).get_car_t_scores()
    except (ValueError, OSError, TypeError):
        config = {}

    def merge(defaults: dict, overrides: dict) -> dict:
        merged = dict(defaults)
        if isinstance(overrides, dict):
            merged.update(overrides)
        return merged

    if not isinstance(config, dict):
        config = {}

    # Dimension-keyed entries (may coexist with category-keyed ones).
    dim_overrides = {dim: config.get(key, {}) for dim, key in _DIMENSION_KEYS.items()}
    has_dimension_keys = any(isinstance(v, dict) and v for v in dim_overrides.values())

    # Category-keyed entries: derive per-gene dimension scores.
    derived: dict[str, dict[str, float]] = {dim: {} for dim in _DIMENSION_KEYS}
    for category, gene_scores in config.items():
        if category in _DIMENSION_KEYS.values() or not isinstance(gene_scores, dict):
            continue
        weights = _category_dimension_weights(category)
        for gene_id, score in gene_scores.items():
            if not isinstance(score, (int, float)):
                continue
            for dim, w in weights.items():
                val = min(10.0, round(w * score, 1))
                if val > derived[dim].get(gene_id, 0.0):
                    derived[dim][gene_id] = val

    if not has_dimension_keys:
        dim_overrides = derived
    else:
        # Prefer explicit dimension values, fill gaps from category derivation.
        for dim in dim_overrides:
            for gene_id, val in derived[dim].items():
                dim_overrides[dim].setdefault(gene_id, val)

    if disease_id == "sle":
        return {
            "b_cell": merge(B_CELL_DEPENDENCY, dim_overrides["b_cell"]),
            "auto_ab": merge(AUTOANTIBODY_ASSOCIATION, dim_overrides["auto_ab"]),
            "plasma": merge(PLASMA_CELL_RELEVANCE, dim_overrides["plasma"]),
            "cd19": merge(CD19_TARGETING, dim_overrides["cd19"]),
            "evidence": merge(CAR_T_EVIDENCE, dim_overrides["evidence"]),
        }
    # Non-SLE modules must use only the active disease's configured rubric.
    # Missing gene/dimension entries are handled as neutral rubric values by
    # score_gene; they never inherit the SLE dictionaries.
    return {dim: dict(values) for dim, values in dim_overrides.items()}


def score_gene(
    gene_id: str,
    gene: dict,
    scoring: dict | None = None,
    disease_id: str = "sle",
) -> CarTGeneScore:
    """Score a single gene for CAR-T therapy suitability.

    Args:
        gene_id: Gene identifier.
        gene: Gene metadata dict.
        scoring: Optional dict of the five scoring sub-dicts (as returned by
            load_config_scoring). Defaults to the hardcoded SLE rubric only
            for SLE; non-SLE callers must pass an active disease rubric.

    Returns dict with individual scores and composite score.
    """
    if scoring is None and disease_id != "sle":
        raise ValueError("non-SLE CAR-T scoring requires an explicit disease rubric")
    scoring = scoring or {
        "b_cell": B_CELL_DEPENDENCY,
        "auto_ab": AUTOANTIBODY_ASSOCIATION,
        "plasma": PLASMA_CELL_RELEVANCE,
        "cd19": CD19_TARGETING,
        "evidence": CAR_T_EVIDENCE,
    }
    b_cell = scoring["b_cell"].get(gene_id, 3.0)
    auto_ab = scoring["auto_ab"].get(gene_id, 3.0)
    plasma = scoring["plasma"].get(gene_id, 3.0)
    cd19 = scoring["cd19"].get(gene_id, 3.0)
    evidence = scoring["evidence"].get(gene_id, 2.0)

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
        "disease_id": gene.get("disease_id", "sle"),
        "function": gene.get("function", "")[:200],
        "disease_evidence": gene.get("disease_evidence", "")[:200],
        "lupus_evidence": gene.get("disease_evidence", gene.get("lupus_evidence", ""))[:200],
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


def compute_all_scores(
    progress_callback: StandardProgress | None = None,
    disease_id: str = "sle",
) -> list[CarTGeneScore]:
    """Score all genes for CAR-T suitability.

    Args:
        progress_callback: Optional ``(step, current, total)`` progress callback.
        disease_id: Disease whose CAR_T_SCORES config is used (defaults to
            the hardcoded SLE rubric, which matches the SLE config exactly).

    Returns list of scored genes sorted by composite score descending.
    """
    from med_research.diseases.coverage import module_coverage

    coverage = module_coverage(disease_id, "car_t", ("genes", "car_t_scores"))
    global last_coverage
    last_coverage = coverage
    if not coverage.is_runnable:
        _tick(progress_callback, "car-t blocked", 1, 1)
        return []

    _tick(progress_callback, "loading genes", 1, 1)
    genes = load_genes(disease_id)
    for gene in genes.values():
        gene["disease_id"] = disease_id
    scoring = load_config_scoring(disease_id)

    total_genes = len(genes)
    results = []
    for i, (gene_id, gene) in enumerate(genes.items(), 1):
        if i % 5 == 0 or i == total_genes:
            _tick(progress_callback, "scoring genes", i, total_genes)
        results.append(score_gene(gene_id, gene, scoring, disease_id=disease_id))

    results.sort(key=lambda x: x["composite_score"], reverse=True)

    _tick(progress_callback, "saving results", 0, 1)
    output_path = disease_output_path(DATA_DIR, "car_t_scores", disease_id)
    write_json_atomic(
        output_path,
        {
            "genes": results,
            "total_genes": len(results),
            "coverage": coverage.to_dict(),
        },
    )

    _tick(progress_callback, "saving results", 1, 1)
    return results


# ── CLI ──────────────────────────────────────────────────────────────────


def analyze(results: list) -> None:
    """Print statistical summary."""
    logger.info("\n" + "=" * 75)
    logger.info("🔬 CAR-T RESPONSE PREDICTOR — Gene-Level Analysis")
    logger.info("=" * 75)

    scores = [r["composite_score"] for r in results]
    logger.info(f"\n  {len(results)} genes scored for CD19 CAR-T suitability")
    logger.info(f"  Score range: {min(scores):.2f} - {max(scores):.2f}")
    logger.info(f"  Mean score: {sum(scores) / len(scores):.2f}")

    tier_counts: dict[str, int] = {}
    for r in results:
        tier_counts[r["tier"]] = tier_counts.get(r["tier"], 0) + 1
    logger.info("\n  Distribution by tier:")
    for tier in [
        "🔴 Tier 1 — Strong CAR-T Candidate",
        "🟠 Tier 2 — Good CAR-T Candidate",
        "🟡 Tier 3 — Possible CAR-T Benefit",
        "🟢 Tier 4 — Limited CAR-T Benefit",
    ]:
        count = tier_counts.get(tier, 0)
        label = tier.split("—")[0].strip()
        logger.info(f"    {label}: {count} genes")


def print_top_genes(results: list, top_n: int = 15) -> None:
    """Print the top N genes by CAR-T suitability."""
    logger.info("\n" + "=" * 75)
    logger.info(f"🎯 TOP {top_n} GENES FOR CD19 CAR-T SUITABILITY")
    logger.info("=" * 75)

    for i, r in enumerate(results[:top_n], 1):
        logger.info(f"\n  #{i} | {r['tier']}")
        logger.info("  " + "─" * 50)
        logger.info(f"  🧬 Gene:     {r['gene_name']}")
        logger.info(f"  📂 Category:  {r.get('category', '')}")
        logger.info(f"  ⭐ Score:     {r['composite_score']:.2f}/10")
        logger.info(f"     ├─ B Cell Dependency:     {r['b_cell_dependency']}/10")
        logger.info(f"     ├─ Autoantibody Assoc:    {r['autoantibody_association']}/10")
        logger.info(f"     ├─ Plasma Cell Relevance: {r['plasma_cell_relevance']}/10")
        logger.info(f"     ├─ CD19 Targeting:        {r['cd19_targeting']}/10")
        logger.info(f"     └─ Clinical Evidence:     {r['clinical_evidence']}/10")
        logger.info(f"  💡 {r['recommendation']}")


def main():
    parser = argparse.ArgumentParser(
        description="CAR-T Response Predictor — Score lupus genes for CD19 CAR-T suitability"
    )
    parser.add_argument("--top", type=int, default=15, help="Number of top genes to display")
    parser.add_argument("--disease", "-d", default="sle", help="Disease ID")
    parser.add_argument("--export-html", action="store_true", help="Generate HTML report")
    args = parser.parse_args()

    results = compute_all_scores(disease_id=args.disease, progress_callback=cli_progress)
    analyze(results)
    print_top_genes(results, args.top)

    if args.export_html:
        from med_research.pipeline.car_t_predictor.report import generate_html_report
        from med_research.pipeline.provenance import build_provenance

        provenance = build_provenance(
            disease_id=args.disease,
            module="car_t_predictor",
            sources=["knowledge_graph"],
            cache_or_live="cache",
            scoring={"ranking": "car_t_heuristic"},
        )
        generate_html_report(results, disease_id=args.disease, provenance=provenance)
        logger.info("\n✅ HTML report generated: car_t_predictor/report.html")

    return results


if __name__ == "__main__":
    import sys

    from med_research.cli import main as cli_main

    sys.exit(cli_main() or 0)
