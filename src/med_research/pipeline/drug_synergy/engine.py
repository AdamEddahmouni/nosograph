"""
Lupus Drug Combination Synergy Prediction Engine

Predicts synergistic drug pairs from the 26-drug knowledge graph library
using a 5-dimensional weighted scoring model.

Scoring Dimensions (each 0-10, weighted):
  1. Target Complementarity (30%): How different are the two drugs' targets?
  2. Pathway Diversity (25%): How diverse are the affected pathways?
  3. Mechanism Orthogonality (20%): How orthogonal are the mechanisms?
  4. Safety Non-overlap (15%): Non-overlapping safety profiles.
  5. Combined Evidence (10%): Existing evidence for combination use.

Usage:
    python drug_synergy/engine.py              # Full analysis
    python drug_synergy/engine.py --top 20     # Top 20 pairs only
    python drug_synergy/engine.py --export-html  # Generate HTML report
"""

import argparse
import json
import sys
from itertools import combinations
from pathlib import Path
from typing import cast

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging

from med_research.cache import disease_output_path, write_json_atomic
from med_research.pipeline.knowledge_graph.config import load_drugs as config_load_drugs
from med_research.pipeline.progress import StandardProgress, _tick, cli_progress
from med_research.pipeline.results import SynergyPair

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

DATA_DIR = Path(__file__).parent / "data"

logger = logging.getLogger(__name__)
last_coverage = None

# ── Mechanism categories for orthogonality scoring ──────────────────────

MECHANISM_CATEGORIES = {
    "Monoclonal Antibody": "Biologic",
    "Monoclonal Antibody Fragment (PEGylated Fab)": "Biologic",
    "Bispecific Antibody": "Biologic",
    "Cellular Therapy (Autologous CAR-T)": "Cellular",
    "Small Molecule": "Small Molecule",
    "Biologic - B Cell Modulation": "B Cell",
    "Biologic - IFN Pathway": "IFN",
    "Immunosuppressant - Calcineurin Inhibitor": "Calcineurin",
    "Immunomodulator - Antimalarial": "Antimalarial",
    "Immunosuppressant - Antimetabolite": "Antimetabolite",
    "Immunosuppressant - Alkylating Agent": "Alkylating",
    "Biologic - B Cell Depletion": "B Cell",
    "Corticosteroid": "Corticosteroid",
    "Biologic - B Cell Depletion (Next-Gen)": "B Cell",
    "Targeted Synthetic - BTK Inhibitor": "BTK",
    "Targeted Synthetic - Complement Inhibitor": "Complement",
    "Immunomodulator - Nrf2 Activator": "Nrf2",
    "Biologic - T Cell Costimulation Blocker": "T Cell Co-Stim",
    "Biologic - Complement Inhibitor": "Complement",
    "Biologic - FcRn Antagonist": "FcRn",
    "Targeted Synthetic - JAK Inhibitor": "JAK",
    "Targeted Synthetic - TYK2 Inhibitor": "TYK2",
    "Biologic - pDC / IFN Pathway": "IFN",
    "Targeted Synthetic - Cereblon Modulator (CELMoD)": "CELMoD",
    "Biologic - Bispecific T Cell Engager (BiTE)": "BiTE",
    "Cellular Therapy - CAR-T Cell": "Cellular",
}

# ── Known combination evidence for bonus scoring ────────────────────────

KNOWN_COMBINATIONS = {
    # (drug_a_id, drug_b_id): evidence_score
    # Note: order doesn't matter – score_combined_evidence checks both directions
    ("belimumab", "rituximab"): 8.0,
    ("belimumab", "hydroxychloroquine"): 7.0,
    ("belimumab", "mycophenolate"): 7.5,
    ("belimumab", "prednisone"): 6.0,
    ("anifrolumab", "hydroxychloroquine"): 6.5,
    ("anifrolumab", "mycophenolate"): 6.5,
    ("voclosporin", "mycophenolate"): 8.0,
    ("voclosporin", "prednisone"): 6.5,
    ("hydroxychloroquine", "mycophenolate"): 7.0,
    ("hydroxychloroquine", "prednisone"): 6.0,
    ("mycophenolate", "prednisone"): 6.0,
    ("mycophenolate", "tacrolimus"): 7.5,
    ("rituximab", "cyclophosphamide"): 7.0,
    ("hydroxychloroquine", "azathioprine"): 6.0,
    ("baricitinib", "hydroxychloroquine"): 6.0,
    ("deucravacitinib", "hydroxychloroquine"): 6.5,
}


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return cast(dict, json.load(f))


def load_drugs(disease_id: str = "sle") -> dict:
    """Load drug data indexed by drug ID."""
    data = config_load_drugs(disease_id)
    return {d["id"]: d for d in data["drugs"]}


def get_mechanism_group(drug: dict) -> str:
    """Return the mechanism group for a drug for orthogonality scoring."""
    category = drug.get("category", "")
    return MECHANISM_CATEGORIES.get(category, cast(str, drug.get("type", "Unknown")))


def score_target_complementarity(drug_a: dict, drug_b: dict) -> float:
    """Score how complementary the drug targets are.

    Different targets attacking the disease from different angles = higher score.
    Same target = low score (redundant), completely different targets = high score.
    """
    target_a = drug_a.get("target", "").lower()
    target_b = drug_b.get("target", "").lower()

    # Same target → low complementarity
    if target_a == target_b:
        return 2.0

    # Both are biologics targeting B cells → somewhat redundant
    cat_a = drug_a.get("category", "")
    cat_b = drug_b.get("category", "")
    if "B Cell" in cat_a and "B Cell" in cat_b and target_a != target_b:
        return 6.0

    # Both target calcineurin → redundant
    if "calcineurin" in target_a and "calcineurin" in target_b:
        return 3.0

    # Different mechanisms = high complementarity
    group_a = get_mechanism_group(drug_a)
    group_b = get_mechanism_group(drug_b)

    if group_a != group_b:
        return 9.5  # different mechanism groups = high complementarity

    # Same group but different targets
    return 7.0


def score_pathway_diversity(drug_a: dict, drug_b: dict) -> float:
    """Score pathway diversity between two drugs.

    Drugs affecting different immune pathways score higher.
    We use mechanism groups as a proxy for pathway involvement.
    """
    group_a = get_mechanism_group(drug_a)
    group_b = get_mechanism_group(drug_b)

    if group_a == group_b:
        # Same mechanism group → lower diversity
        if drug_a.get("type") == drug_b.get("type"):
            return 3.0  # Same type + same group
        return 5.0  # Same group but different type

    # Different mechanism groups → high diversity
    # Bonus if one is biologic and one is small molecule
    type_a = drug_a.get("type", "")
    type_b = drug_b.get("type", "")
    if "Monoclonal" in type_a and "Small" in type_b:
        return 10.0
    if "Small" in type_a and "Monoclonal" in type_b:
        return 10.0
    if "Cellular" in type_a or "Cellular" in type_b:
        return 9.0

    return 8.0


def score_mechanism_orthogonality(drug_a: dict, drug_b: dict) -> float:
    """Score how orthogonal the mechanisms of action are.

    Orthogonal mechanisms attack the disease from independent angles.
    """
    group_a = get_mechanism_group(drug_a)
    group_b = get_mechanism_group(drug_b)

    if group_a == group_b:
        return 2.0  # Same mechanism = not orthogonal

    # Score based on how different the mechanisms are
    mechanism_pairs = {
        ("B Cell", "IFN"): 9.0,
        ("B Cell", "JAK"): 8.0,
        ("B Cell", "TYK2"): 8.0,
        ("B Cell", "Complement"): 8.5,
        ("B Cell", "BTK"): 9.0,
        ("B Cell", "T Cell Co-Stim"): 9.0,
        ("B Cell", "Cellular"): 10.0,
        ("IFN", "JAK"): 7.0,
        ("IFN", "TYK2"): 6.0,
        ("IFN", "Complement"): 8.0,
        ("IFN", "Cellular"): 9.0,
        ("Calcineurin", "B Cell"): 7.0,
        ("Calcineurin", "IFN"): 7.0,
        ("Calcineurin", "JAK"): 6.5,
        ("Calcineurin", "Complement"): 7.0,
        ("Antimetabolite", "B Cell"): 8.0,
        ("Antimetabolite", "IFN"): 7.0,
        ("Antimetabolite", "Complement"): 7.5,
        ("Corticosteroid", "B Cell"): 6.0,
        ("Corticosteroid", "IFN"): 6.0,
        ("Complement", "JAK"): 7.0,
        ("Complement", "TYK2"): 7.0,
        ("Complement", "Cellular"): 9.0,
        ("JAK", "TYK2"): 2.0,
        ("JAK", "Cellular"): 9.0,
        ("TYK2", "Cellular"): 9.0,
        ("BTK", "IFN"): 8.0,
        ("BTK", "Cellular"): 9.0,
        ("FcRn", "B Cell"): 8.0,
        ("FcRn", "IFN"): 8.0,
        ("CELMoD", "B Cell"): 8.0,
        ("CELMoD", "IFN"): 8.0,
        ("BiTE", "B Cell"): 6.0,
        ("BiTE", "IFN"): 8.0,
        ("Cellular", "B Cell"): 10.0,
        ("Cellular", "Complement"): 9.0,
    }

    key = (min(group_a, group_b), max(group_a, group_b))
    return mechanism_pairs.get(key, 5.0)


def score_safety_non_overlap(drug_a: dict, drug_b: dict) -> float:
    """Score based on non-overlapping safety profiles.

    Drugs with different safety profiles score higher (less cumulative toxicity).
    We use mechanism group and type as proxies for safety profile.
    """
    group_a = get_mechanism_group(drug_a)
    group_b = get_mechanism_group(drug_b)

    if group_a == group_b:
        # Same mechanism group → likely overlapping toxicities
        if drug_a.get("type") == drug_b.get("type"):
            return 1.0  # Very likely overlapping
        return 3.0

    # Both immunosuppressive → some overlap risk
    immunosuppressive_groups = {"Calcineurin", "Antimetabolite", "Alkylating", "Corticosteroid"}
    if group_a in immunosuppressive_groups and group_b in immunosuppressive_groups:
        return 4.0

    # Biologics generally have good safety profiles
    is_biologic_a = "Monoclonal" in drug_a.get("type", "") or "Bispecific" in drug_a.get("type", "")
    is_biologic_b = "Monoclonal" in drug_b.get("type", "") or "Bispecific" in drug_b.get("type", "")

    if is_biologic_a and is_biologic_b:
        return 5.0  # Biologics generally well tolerated, some infection risk overlap

    if (is_biologic_a and group_b in {"JAK", "TYK2", "BTK"}) or (
        is_biologic_b and group_a in {"JAK", "TYK2", "BTK"}
    ):
        return 7.0  # Biologic + targeted oral → different safety concerns

    # Small molecule + biologic = generally non-overlapping
    type_a = drug_a.get("type", "")
    type_b = drug_b.get("type", "")
    if ("Small" in type_a and "Monoclonal" in type_b) or (
        "Monoclonal" in type_a and "Small" in type_b
    ):
        return 8.0

    return 6.0


def score_combined_evidence(drug_a: dict, drug_b: dict) -> float:
    """Score based on existing evidence for this combination."""
    key = (drug_a["id"], drug_b["id"])
    reverse_key = (drug_b["id"], drug_a["id"])

    if key in KNOWN_COMBINATIONS:
        return KNOWN_COMBINATIONS[key]
    if reverse_key in KNOWN_COMBINATIONS:
        return KNOWN_COMBINATIONS[reverse_key]

    # Check if both are approved for lupus → likely some clinical overlap
    approval_a = drug_a.get("approval", "")
    approval_b = drug_b.get("approval", "")

    lupus_terms = ["SLE", "lupus", "lupus nephritis"]
    a_lupus = any(term.lower() in approval_a.lower() for term in lupus_terms)
    b_lupus = any(term.lower() in approval_b.lower() for term in lupus_terms)

    if a_lupus and b_lupus:
        return 5.0  # Both approved for lupus → some real-world evidence
    if a_lupus or b_lupus:
        return 3.0  # One approved for lupus

    return 1.0  # No known evidence


def score_drug_pair(drug_a: dict, drug_b: dict) -> SynergyPair:
    """Score a single drug pair across all 5 dimensions.

    Returns:
        dict with individual scores and composite score.
    """
    target_comp = score_target_complementarity(drug_a, drug_b)
    pathway_div = score_pathway_diversity(drug_a, drug_b)
    mech_ortho = score_mechanism_orthogonality(drug_a, drug_b)
    safety = score_safety_non_overlap(drug_a, drug_b)
    evidence = score_combined_evidence(drug_a, drug_b)

    weights = {
        "target_complementarity": 0.30,
        "pathway_diversity": 0.25,
        "mechanism_orthogonality": 0.20,
        "safety_non_overlap": 0.15,
        "combined_evidence": 0.10,
    }

    composite = (
        target_comp * weights["target_complementarity"]
        + pathway_div * weights["pathway_diversity"]
        + mech_ortho * weights["mechanism_orthogonality"]
        + safety * weights["safety_non_overlap"]
        + evidence * weights["combined_evidence"]
    )

    return {
        "drug_a_id": drug_a["id"],
        "drug_a_name": drug_a["name"],
        "drug_b_id": drug_b["id"],
        "drug_b_name": drug_b["name"],
        "target_complementarity": round(target_comp, 1),
        "pathway_diversity": round(pathway_div, 1),
        "mechanism_orthogonality": round(mech_ortho, 1),
        "safety_non_overlap": round(safety, 1),
        "combined_evidence": round(evidence, 1),
        "composite_score": round(composite, 2),
        "drug_a_type": drug_a.get("type", ""),
        "drug_b_type": drug_b.get("type", ""),
        "drug_a_mechanism": drug_a.get("mechanism", "")[:200],
        "drug_b_mechanism": drug_b.get("mechanism", "")[:200],
        "drug_a_category": drug_a.get("category", ""),
        "drug_b_category": drug_b.get("category", ""),
    }


def score_drug_pairs(
    drugs: dict,
    progress_callback: StandardProgress | None = None,
) -> list[SynergyPair]:
    """Score all unique drug pairs.

    Args:
        drugs: Dict of drug data indexed by drug ID.
        progress_callback: Optional ``(step, current, total)`` progress callback.

    Returns:
        List of scored pairs sorted by composite score descending.
    """
    drug_list = list(drugs.values())
    total_pairs = len(drug_list) * (len(drug_list) - 1) // 2

    pairs = []
    for i, (drug_a, drug_b) in enumerate(combinations(drug_list, 2), 1):
        if total_pairs and (i % 50 == 0 or i == total_pairs):
            _tick(progress_callback, "scoring drug pairs", i, total_pairs)
        pairs.append(score_drug_pair(drug_a, drug_b))

    # Sort by composite score descending
    pairs.sort(key=lambda x: x["composite_score"], reverse=True)

    # Assign tiers
    for p in pairs:
        if p["composite_score"] >= 8.0:
            p["tier"] = "🔴 Tier 1 — Strong Synergy Potential"
        elif p["composite_score"] >= 7.0:
            p["tier"] = "🟠 Tier 2 — Promising Synergy"
        elif p["composite_score"] >= 6.0:
            p["tier"] = "🟡 Tier 3 — Possible Synergy"
        else:
            p["tier"] = "🟢 Tier 4 — Limited Synergy"

    _tick(progress_callback, "scoring drug pairs", total_pairs or 1, total_pairs or 1)

    return pairs


def analyze(scored_pairs: list) -> None:
    """Print statistical summary of scored pairs."""
    logger.info("\n" + "=" * 75)
    logger.info("📊 DRUG SYNERGY ANALYSIS SUMMARY")
    logger.info("=" * 75)

    tier_counts: dict[str, int] = {}
    for p in scored_pairs:
        tier_counts[p["tier"]] = tier_counts.get(p["tier"], 0) + 1

    logger.info(f"\n  Total drug pairs evaluated: {len(scored_pairs)}")
    scores = [p["composite_score"] for p in scored_pairs]
    logger.info(f"  Score range: {min(scores):.2f} - {max(scores):.2f}")
    logger.info(f"  Mean score: {sum(scores) / len(scores):.2f}")
    logger.info("\n  Distribution by tier:")
    for tier in [
        "🔴 Tier 1 — Strong Synergy Potential",
        "🟠 Tier 2 — Promising Synergy",
        "🟡 Tier 3 — Possible Synergy",
        "🟢 Tier 4 — Limited Synergy",
    ]:
        count = tier_counts.get(tier, 0)
        label = tier.split("—")[0].strip()
        logger.info(f"    {label}: {count} pairs")

    # Top drugs appearing most in top pairs
    drug_mentions: dict[str, int] = {}
    for p in scored_pairs[:50]:
        drug_mentions[p["drug_a_name"]] = drug_mentions.get(p["drug_a_name"], 0) + 1
        drug_mentions[p["drug_b_name"]] = drug_mentions.get(p["drug_b_name"], 0) + 1

    logger.info("\n  Most versatile drugs (appearing most in top-50 pairs):")
    for drug_name, count in sorted(drug_mentions.items(), key=lambda x: x[1], reverse=True)[:8]:
        logger.info(f"    {drug_name}: {count} synergistic pairings")


def print_top_pairs(scored_pairs: list, top_n: int = 15) -> None:
    """Print the top N synergistic drug pairs."""
    logger.info("\n" + "=" * 75)
    logger.info(f"🏆 TOP {top_n} SYNERGISTIC DRUG PAIRS")
    logger.info("=" * 75)

    for i, p in enumerate(scored_pairs[:top_n], 1):
        logger.info(f"\n  #{i} | {p['tier']}")
        logger.info("  " + "─" * 50)
        logger.info(f"  💊 Drug A:  {p['drug_a_name']}")
        logger.info(f"  💊 Drug B:  {p['drug_b_name']}")
        logger.info(f"  ⭐ Score:   {p['composite_score']:.2f}/10")
        logger.info(f"     ├─ Target Complementarity:   {p['target_complementarity']}/10")
        logger.info(f"     ├─ Pathway Diversity:        {p['pathway_diversity']}/10")
        logger.info(f"     ├─ Mechanism Orthogonality:  {p['mechanism_orthogonality']}/10")
        logger.info(f"     ├─ Safety Non-overlap:       {p['safety_non_overlap']}/10")
        logger.info(f"     └─ Combined Evidence:        {p['combined_evidence']}/10")


def compute_synergy(
    progress_callback: StandardProgress | None = None,
    disease_id: str = "sle",
    save: bool = True,
) -> list[SynergyPair]:
    """Main entry point: load drugs, score all pairs, return results.

    Args:
        progress_callback: Optional ``(step, current, total)`` progress callback.
        disease_id: Disease whose drug library is used.
        save: When False, compute in memory without writing the shared
            synergy_results.json (used by the comparative cross-disease run
            so per-disease scoring doesn't clobber the last-run results).
    """
    from med_research.diseases.coverage import module_coverage

    global last_coverage
    coverage = module_coverage(disease_id, "synergy", ("genes", "drugs"))
    last_coverage = coverage
    if not coverage.is_runnable:
        _tick(progress_callback, "synergy blocked", 1, 1)
        return []

    _tick(progress_callback, "loading drug library", 1, 3)
    drugs = load_drugs(disease_id)

    _tick(progress_callback, "loading drug library", 2, 3)

    pairs = score_drug_pairs(drugs, progress_callback=progress_callback)

    if save:
        _tick(progress_callback, "saving results", 2, 3)
        output_path = disease_output_path(DATA_DIR, "synergy_results", disease_id)
        write_json_atomic(output_path, {"pairs": pairs, "total_pairs": len(pairs)})
        _tick(progress_callback, "saving results", 3, 3)
    else:
        _tick(progress_callback, "synergy complete", 3, 3)
    return pairs


def main():
    parser = argparse.ArgumentParser(description="Lupus Drug Combination Synergy Predictor")
    parser.add_argument("--top", type=int, default=15, help="Number of top pairs to display")
    parser.add_argument("--disease", "-d", default="sle", help="Disease ID (default: sle)")
    parser.add_argument("--export-html", action="store_true", help="Generate HTML report")
    args = parser.parse_args()

    pairs = compute_synergy(disease_id=args.disease, progress_callback=cli_progress)
    analyze(pairs)
    print_top_pairs(pairs, args.top)

    if args.export_html:
        from med_research.pipeline.drug_synergy.report import generate_html_report
        from med_research.pipeline.provenance import build_provenance

        provenance = build_provenance(
            disease_id=args.disease,
            module="drug_synergy",
            sources=["knowledge_graph"],
            cache_or_live="cache",
            scoring={"ranking": "composite_score"},
        )
        generate_html_report(pairs, disease_id=args.disease, provenance=provenance)
        logger.info("\n✅ HTML report generated: drug_synergy/report.html")

    return pairs


if __name__ == "__main__":
    import sys

    from med_research.cli import main as cli_main

    sys.exit(cli_main() or 0)

