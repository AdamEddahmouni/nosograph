"""
Lupus Drug Repurposing Engine

Multi-modal scoring system that evaluates drug repurposing candidates
for the 13 untargeted lupus genes identified by the knowledge graph.

Scoring Dimensions (each 0-10, weighted):
  1. Target Similarity (20%): How closely related is the drug's known target to the gene?
  2. Pathway Proximity (15%): Network distance in the knowledge graph.
  3. Mechanistic Rationale (20%): Does the drug's mechanism make biological sense?
  4. Clinical Evidence (15%): Literature/trial support level.
  5. Adverse Event Profile (20%): Lupus-specific safety scoring from curated profiles.
  6. Novelty Bonus (10%): How novel is this repurposing application? (0-5)

Usage:
    python engine.py              # Full analysis
    python engine.py --top 10     # Top 10 candidates only
    python engine.py --gene BTK   # Candidates for a specific gene
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import networkx as nx

# Add parent to path for knowledge_graph import
sys.path.insert(0, str(Path(__file__).parent.parent))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from med_research.pipeline.knowledge_graph.config import load_drugs as config_load_drugs
from med_research.pipeline.knowledge_graph.config import load_genes as config_load_genes
from med_research.pipeline.knowledge_graph.config import load_pathways as config_load_pathways
import logging

DATA_DIR = Path(__file__).parent / "data"

logger = logging.getLogger(__name__)
last_coverage = None


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_knowledge_graph(disease_id: str = "sle"):
    """Load the knowledge graph using the existing build_graph module."""
    from med_research.pipeline.knowledge_graph.builder import build_graph
    return build_graph(disease_id)


def load_genes(disease_id: str = "sle"):
    """Load gene data indexed by gene ID."""
    data = config_load_genes(disease_id)
    return {g["id"]: g for g in data["genes"]}


def load_drugs(disease_id: str = "sle"):
    """Load drug data indexed by drug ID."""
    data = config_load_drugs(disease_id)
    return {d["id"]: d for d in data["drugs"]}


def load_pathways(disease_id: str = "sle"):
    """Load pathway data indexed by pathway ID."""
    data = config_load_pathways(disease_id)
    return {p["id"]: p for p in data["pathways"]}


def compute_pathway_proximity(G, gene_id: str, candidate: dict) -> float:
    """
    Compute pathway proximity score using shortest path in the knowledge graph.

    We look at the distance between the gene node and the drug's target nodes
    (if the drug exists in the graph), or pathway-level proximity.
    """
    # Preserve the graph lookup contract: an unknown gene should fail loudly.
    G.nodes[gene_id]

    # If the drug is in our knowledge graph, use network distance
    drug_nodes = [
        n
        for n, d in G.nodes(data=True)
        if d.get("type") == "drug"
        and candidate["drug_name"].lower().split("(")[0].strip()
        in d.get("label", "").lower()
    ]

    if drug_nodes and gene_id in G:
        try:
            distances = []
            for dn in drug_nodes:
                dist = nx.shortest_path_length(G, source=dn, target=gene_id)
                distances.append(dist)
            min_dist = min(distances) if distances else 5
            # Convert distance to score (closer = higher score)
            # Distance 1-2 = score 10, distance 3 = 8, 4 = 6, 5 = 4, >5 = 2
            if min_dist <= 1:
                return 10.0
            elif min_dist == 2:
                return 9.0
            elif min_dist == 3:
                return 7.0
            elif min_dist == 4:
                return 5.0
            else:
                return max(2.0, 10.0 - min_dist * 1.5)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            pass

    # If drug is not in graph, score based on the candidate's curated score
    return candidate.get("pathway_proximity_score", 5.0)


def identify_untargeted_genes(G, disease_id: str = "sle") -> list:
    """Identify active-disease genes with no direct drug targeting them."""
    targeted_genes = set()
    for _, v, d in G.edges(data=True):
        if d.get("type") == "TARGETS" and G.nodes[v].get("type") == "gene":
            targeted_genes.add(v)

    untargeted = []
    for node, data in G.nodes(data=True):
        if data.get("type") == "gene" and node not in targeted_genes:
            untargeted.append(
                {
                    "id": node,
                    "name": data.get("label", node),
                    "function": data.get("description", ""),
                    "lupus_evidence": data.get("disease_evidence", data.get("lupus_evidence", "")),
                    "disease_evidence": data.get("disease_evidence", data.get("lupus_evidence", "")),
                    "odds_ratio": data.get("odds_ratio"),
                    "category": data.get("category", ""),
                    "chromosome": data.get("chromosome", ""),
                }
            )

    # Filter out drug-target genes (CD20, IMPDH, Calcineurin, Glucocorticoid Receptor)
    # These aren't lupus risk genes - they're drug targets we added
    from med_research.diseases.base import Disease
    excluded = Disease(disease_id).get_drug_target_exclusions()
    untargeted = [g for g in untargeted if g["id"] not in excluded]

    return untargeted


def compute_composite_score(candidate: dict) -> float:
    """
    Compute weighted composite score from all dimensions.

    Weights (updated: safety replaced by adverse event profile at 20%):
        Target Similarity: 20%
        Pathway Proximity: 15%
        Mechanistic Rationale: 20%
        Clinical Evidence: 15%
        Adverse Event Profile: 20%
        Novelty Bonus: 10%
    """
    weights = {
        "target_similarity_score": 0.20,
        "pathway_proximity_score": 0.15,
        "mechanistic_rationale_score": 0.20,
        "clinical_evidence_score": 0.15,
        "adverse_event_score": 0.20,
        "novelty_score": 0.10,
    }

    # Fall back to legacy safety_score if adverse_event_score not set
    ae_score = candidate.get("adverse_event_score")
    if ae_score is None:
        ae_score = candidate.get("safety_score", 5)

    composite = 0.0
    for key, weight in weights.items():
        score = ae_score if key == "adverse_event_score" else candidate.get(key, 5)
        composite += score * weight

    return round(composite, 2)


def score_candidates(G, candidates: list, genes: dict, disease_id: str = "sle") -> list:
    """Score all repurposing candidates and compute composite scores."""
    scored = []
    drugs = load_drugs(disease_id)  # Load active-disease drugs for AE matching

    for candidate in candidates:
        gene_id = candidate["gene_id"]
        gene_info = genes.get(gene_id, {})

        # Compute pathway proximity from the knowledge graph
        try:
            kg_proximity = compute_pathway_proximity(G, gene_id, candidate)
        except (nx.NetworkXNoPath, nx.NodeNotFound, KeyError, ValueError):
            kg_proximity = candidate.get("pathway_proximity_score", 5.0)

        # Use the higher of curated score and computed proximity
        curated_proximity = candidate.get("pathway_proximity_score", 5.0)
        final_proximity = max(kg_proximity, curated_proximity)

        # Compute adverse event score from profiler if available
        adverse_score = candidate.get("safety_score", 5)
        try:
            from med_research.pipeline.adverse_events.profiler import (
                compute_adverse_event_score,
                load_profiles,
            )
            # Match by drug ID from the KG drugs dict (same IDs as profiles)
            for drug_id, drug_data in drugs.items():
                if drug_data.get("name", "").lower() in candidate["drug_name"].lower() or \
                   candidate["drug_name"].lower().split("(")[0].strip() in drug_data.get("name", "").lower():
                    profile_result = compute_adverse_event_score(load_profiles().get(drug_id, {}), disease_id)
                    if profile_result and "composite_safety_score" in profile_result:
                        adverse_score = profile_result["composite_safety_score"]
                    break
        except ImportError:
            pass
        except KeyError:
            pass
        candidate["adverse_event_score"] = adverse_score

        composite = compute_composite_score(candidate)

        scored.append(
            {
                **candidate,
                "kg_pathway_proximity": round(kg_proximity, 1),
                "final_proximity": round(final_proximity, 1),
                "composite_score": composite,
                "gene_name": gene_info.get("name", gene_id),
                "gene_category": gene_info.get("category", ""),
                "gene_function": gene_info.get("function", ""),
                "gene_lupus_evidence": gene_info.get("disease_evidence", gene_info.get("lupus_evidence", "")),
                "gene_disease_evidence": gene_info.get("disease_evidence", gene_info.get("lupus_evidence", "")),
                "gene_odds_ratio": gene_info.get("odds_ratio"),
            }
        )

    # Sort by composite score descending
    scored.sort(key=lambda x: x["composite_score"], reverse=True)

    # Assign priority tiers
    for c in scored:
        if c["composite_score"] >= 8.0:
            c["tier"] = "🔴 Tier 1 — Highest Priority"
        elif c["composite_score"] >= 7.0:
            c["tier"] = "🟠 Tier 2 — High Priority"
        elif c["composite_score"] >= 6.0:
            c["tier"] = "🟡 Tier 3 — Medium Priority"
        else:
            c["tier"] = "🟢 Tier 4 — Lower Priority"

    return scored


def analyze(scored_candidates: list):
    """Print statistical summary of scored candidates."""
    logger.info("\n" + "=" * 75)
    logger.info("📊 REPURPOSING ANALYSIS SUMMARY")
    logger.info("=" * 75)

    # By tier
    tier_counts = defaultdict(int)
    for c in scored_candidates:
        tier_counts[c["tier"]] += 1

    logger.info(f"\n  Total candidates evaluated: {len(scored_candidates)}")
    logger.info(f"  Score range: {min(c['composite_score'] for c in scored_candidates):.2f} - {max(c['composite_score'] for c in scored_candidates):.2f}")
    logger.info("\n  Distribution by priority tier:")
    for tier in ["🔴 Tier 1 — Highest Priority", "🟠 Tier 2 — High Priority", "🟡 Tier 3 — Medium Priority", "🟢 Tier 4 — Lower Priority"]:
        count = tier_counts[tier]
        if count > 0:
            logger.info(f"    {tier}: {count} candidates")

    # By gene
    gene_counts = defaultdict(int)
    gene_scores = defaultdict(list)
    for c in scored_candidates:
        gene_counts[c["gene_name"]] += 1
        gene_scores[c["gene_name"]].append(c["composite_score"])

    logger.info("\n  Genes with most repurposing candidates:")
    for gene_name, count in sorted(gene_counts.items(), key=lambda x: x[1], reverse=True):
        avg = sum(gene_scores[gene_name]) / len(gene_scores[gene_name])
        logger.info(f"    {gene_name}: {count} candidates (avg score: {avg:.2f})")

    # Top unique drugs
    drug_scores = defaultdict(list)
    for c in scored_candidates:
        drug_scores[c["drug_name"]].append(c["composite_score"])

    logger.info("\n  Most promising drugs (across multiple genes):")
    multi_gene_drugs = [
        (drug, scores)
        for drug, scores in drug_scores.items()
        if len(scores) >= 2
    ]
    multi_gene_drugs.sort(key=lambda x: sum(x[1]) / len(x[1]), reverse=True)
    for drug, scores in multi_gene_drugs[:8]:
        logger.info(f"    {drug}: targets {len(scores)} genes (avg: {sum(scores)/len(scores):.2f})")


def print_top_candidates(scored_candidates: list, top_n: int = 10):
    """Print the top N repurposing candidates."""
    logger.info("\n" + "=" * 75)
    logger.info(f"🏆 TOP {top_n} REPURPOSING CANDIDATES")
    logger.info("=" * 75)

    for i, c in enumerate(scored_candidates[:top_n], 1):
        logger.info(f"\n  #{i} | {c['tier']}")
        logger.info("  ─────────────────────────────────────────────")
        logger.info(f"  💊 Drug:      {c['drug_name']}")
        logger.info(f"  🧬 Gene:      {c['gene_name']} ({c['gene_id']})")
        logger.info(f"  📂 Category:  {c['gene_category']}")
        logger.info(f"  ⭐ Score:     {c['composite_score']:.2f}/10")
        logger.info(f"     ├─ Target Similarity:     {c['target_similarity_score']}/10")
        logger.info(f"     ├─ Pathway Proximity:     {c['final_proximity']:.1f}/10")
        logger.info(f"     ├─ Mechanistic Rationale: {c['mechanistic_rationale_score']}/10")
        logger.info(f"     ├─ Clinical Evidence:     {c['clinical_evidence_score']}/10")
        logger.info(f"     ├─ Adverse Event Profile:  {c.get('adverse_event_score', c.get('safety_score', 'N/A'))}/10")
        logger.info(f"     └─ Novelty Bonus:         {c['novelty_score']}/5")
        logger.info(f"  📋 Evidence:   {c['evidence_level']}")
        logger.info(f"  🔬 Mechanism:  {c['mechanism'][:150]}...")
        logger.info(f"  💡 Rationale:  {c['rationale'][:180]}...")
        logger.info(f"  🚦 Status:     {c['status']}")


def print_gene_analysis(scored_candidates: list, genes: dict, gene_id: str):
    """Print detailed analysis for a specific gene."""
    gene = genes.get(gene_id, {})
    gene_candidates = [c for c in scored_candidates if c["gene_id"] == gene_id]

    logger.info("\n" + "=" * 75)
    logger.info(f"🧬 GENE-FOCUSED ANALYSIS: {gene.get('name', gene_id)}")
    logger.info("=" * 75)
    logger.info(f"\n  Function:        {gene.get('function', 'N/A')}")
    logger.info(f"  Category:        {gene.get('category', 'N/A')}")
    logger.info(f"  Chromosome:      {gene.get('chromosome', 'N/A')}")
    logger.info(f"  Odds Ratio:      {gene.get('odds_ratio', 'N/A')}")
    logger.info(f"  Lupus Evidence:  {gene.get('lupus_evidence', 'N/A')[:200]}")

    if not gene_candidates:
        logger.warning("\n  ⚠️  No repurposing candidates found for this gene.")
        return

    logger.info(f"\n  📋 {len(gene_candidates)} repurposing candidates:")
    for i, c in enumerate(gene_candidates, 1):
        logger.info(f"\n    {i}. {c['drug_name']} | Score: {c['composite_score']:.2f} | {c['tier']}")
        logger.info(f"       Mechanism: {c['mechanism'][:120]}...")
        logger.info(f"       Rationale: {c['rationale'][:150]}...")
        logger.info(f"       Evidence:  {c['evidence_level']}")
        logger.info(f"       Status:    {c['status']}")


def main():
    parser = argparse.ArgumentParser(
        description="Drug Repurposing Engine — Multi-modal scoring for untargeted genes"
    )
    parser.add_argument("--disease", type=str, default="sle",
                        help="Disease ID (default: sle)")
    parser.add_argument("--top", type=int, default=15, help="Number of top candidates to display")
    parser.add_argument("--gene", type=str, help="Focus analysis on a specific gene ID")
    parser.add_argument("--export-html", action="store_true", help="Export HTML report")
    args = parser.parse_args()

    from med_research.diseases.coverage import module_coverage

    global last_coverage
    coverage = module_coverage(
        args.disease, "repurposing", ("genes", "drugs", "relationships")
    )
    last_coverage = coverage
    if not coverage.is_runnable:
        logger.error(
            f"❌ Drug repurposing blocked for {args.disease}: "
            f"{', '.join(coverage.missing_inputs)}"
        )
        return []

    logger.info(f"🔄 Loading {args.disease.upper()} knowledge graph...")
    G = load_knowledge_graph(args.disease)
    logger.info(f"   Graph loaded: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    logger.info("🔄 Loading gene and candidate data...")
    genes = load_genes(args.disease)
    candidates_data = load_json(DATA_DIR / "candidates.json")
    candidates = candidates_data["repurposing_candidates"]
    logger.info(f"   Loaded {len(genes)} genes, {len(candidates)} repurposing candidates")

    logger.info(f"🔄 Identifying untargeted {args.disease.upper()} genes...")
    untargeted = identify_untargeted_genes(G, args.disease)
    untargeted_ids = {g["id"] for g in untargeted}
    logger.info(f"   Found {len(untargeted)} untargeted lupus genes:")
    for g in untargeted:
        logger.info(f"     • {g['name']} ({g['id']}) — {g.get('category', '')}")

    logger.info("🔄 Scoring candidates...")
    scored = score_candidates(G, candidates, genes, disease_id=args.disease)

    # Filter to only candidates for actually untargeted genes
    scored = [c for c in scored if c["gene_id"] in untargeted_ids]
    logger.info(f"   Scored {len(scored)} candidates across {len(set(c['gene_id'] for c in scored))} genes")

    analyze(scored)

    if args.gene:
        print_gene_analysis(scored, genes, args.gene)
    else:
        print_top_candidates(scored, args.top)

    if args.export_html:
        from med_research.pipeline.drug_repurposing.report import generate_html_report
        generate_html_report(scored, untargeted, genes, G, disease_id=args.disease)
        logger.info("\n✅ HTML report generated: drug_repurposing/report.html")

    return scored


if __name__ == "__main__":
    scored = main()
