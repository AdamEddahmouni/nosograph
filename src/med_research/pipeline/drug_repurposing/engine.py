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

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import networkx as nx

from med_research.logging_config import get_logger
from med_research.pipeline.knowledge_graph.config import load_drugs as config_load_drugs
from med_research.pipeline.knowledge_graph.config import load_genes as config_load_genes
from med_research.pipeline.knowledge_graph.config import load_pathways as config_load_pathways
from med_research.types import CandidateDict, GeneDict

logger = get_logger(__name__)

DATA_DIR = Path(__file__).parent / "data"


def load_json(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_knowledge_graph(disease_id: str = "sle"):
    """Load the knowledge graph using the existing build_graph module."""
    from med_research.pipeline.knowledge_graph.builder import build_graph
    return build_graph(disease_id)


def load_genes(disease_id: str = "sle") -> dict[str, GeneDict]:
    """Load gene data indexed by gene ID."""
    data = config_load_genes(disease_id)
    return {g["id"]: g for g in data["genes"]}


def load_drugs(disease_id: str = "sle") -> dict[str, Any]:
    """Load drug data indexed by drug ID."""
    data = config_load_drugs(disease_id)
    return {d["id"]: d for d in data["drugs"]}


def load_pathways(disease_id: str = "sle") -> dict[str, Any]:
    """Load pathway data indexed by pathway ID."""
    data = config_load_pathways(disease_id)
    return {p["id"]: p for p in data["pathways"]}


def compute_pathway_proximity(G: nx.MultiDiGraph, gene_id: str, candidate: dict[str, Any]) -> float:
    """
    Compute pathway proximity score using shortest path in the knowledge graph.

    We look at the distance between the gene node and the drug's target nodes
    (if the drug exists in the graph), or pathway-level proximity.
    """

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


def identify_untargeted_genes(G: nx.MultiDiGraph) -> list[dict[str, Any]]:
    """Identify lupus-associated genes with no direct drug targeting them."""
    targeted_genes = set()
    for _u, v, d in G.edges(data=True):
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
                    "lupus_evidence": data.get("lupus_evidence", ""),
                    "odds_ratio": data.get("odds_ratio"),
                    "category": data.get("category", ""),
                    "chromosome": data.get("chromosome", ""),
                }
            )

    # Filter out drug-target genes (CD20, IMPDH, Calcineurin, Glucocorticoid Receptor)
    # These aren't lupus risk genes - they're drug targets we added
    drug_target_genes = {"CD20", "IMPDH", "Calcineurin", "Glucocorticoid Receptor"}
    untargeted = [g for g in untargeted if g["id"] not in drug_target_genes]

    return untargeted


def compute_composite_score(candidate: dict[str, Any]) -> float:
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


def score_candidates(
    G: nx.MultiDiGraph,
    candidates: list[dict[str, Any]],
    genes: dict[str, GeneDict],
) -> list[CandidateDict]:
    """Score all repurposing candidates and compute composite scores."""
    scored = []
    drugs = load_drugs()  # Load KG drugs for AE score matching

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
            from med_research.pipeline.adverse_events.profiler import get_drug_profile
            # Match by drug ID from the KG drugs dict (same IDs as profiles)
            for drug_id, drug_data in drugs.items():
                if drug_data.get("name", "").lower() in candidate["drug_name"].lower() or \
                   candidate["drug_name"].lower().split("(")[0].strip() in drug_data.get("name", "").lower():
                    profile_result = get_drug_profile(drug_id)
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
                "gene_lupus_evidence": gene_info.get("lupus_evidence", ""),
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


def analyze(scored_candidates: list[CandidateDict]) -> None:
    """Log statistical summary of scored candidates."""
    logger.info("=" * 75)
    logger.info("REPURPOSING ANALYSIS SUMMARY")
    logger.info("=" * 75)

    tier_counts = defaultdict(int)
    for c in scored_candidates:
        tier_counts[c["tier"]] += 1

    logger.info("  Total candidates evaluated: %d", len(scored_candidates))
    logger.info("  Score range: %.2f - %.2f", min(c['composite_score'] for c in scored_candidates), max(c['composite_score'] for c in scored_candidates))
    logger.info("  Distribution by priority tier:")
    _TIERS = [
        "🔴 Tier 1 — Highest Priority",
        "🟠 Tier 2 — High Priority",
        "🟡 Tier 3 — Medium Priority",
        "🟢 Tier 4 — Lower Priority",
    ]
    for tier in _TIERS:
        count = tier_counts.get(tier, 0)
        if count > 0:
            logger.info("    %s: %d candidates", tier, count)

    gene_counts = defaultdict(int)
    gene_scores = defaultdict(list)
    for c in scored_candidates:
        gene_counts[c["gene_name"]] += 1
        gene_scores[c["gene_name"]].append(c["composite_score"])

    logger.info("  Genes with most repurposing candidates:")
    for gene_name, count in sorted(gene_counts.items(), key=lambda x: x[1], reverse=True):
        avg = sum(gene_scores[gene_name]) / len(gene_scores[gene_name])
        logger.info("    %s: %d candidates (avg score: %.2f)", gene_name, count, avg)

    drug_scores = defaultdict(list)
    for c in scored_candidates:
        drug_scores[c["drug_name"]].append(c["composite_score"])

    logger.info("  Most promising drugs (across multiple genes):")
    multi_gene_drugs = [
        (drug, scores)
        for drug, scores in drug_scores.items()
        if len(scores) >= 2
    ]
    multi_gene_drugs.sort(key=lambda x: sum(x[1]) / len(x[1]), reverse=True)
    for drug, scores in multi_gene_drugs[:8]:
        logger.info("    %s: targets %d genes (avg: %.2f)", drug, len(scores), sum(scores)/len(scores))


def print_top_candidates(scored_candidates: list[CandidateDict], top_n: int = 10) -> None:
    """Log the top N repurposing candidates."""
    logger.info("=" * 75)
    logger.info("TOP %d REPURPOSING CANDIDATES", top_n)
    logger.info("=" * 75)

    for i, c in enumerate(scored_candidates[:top_n], 1):
        logger.info("  #%d | %s", i, c['tier'])
        logger.info("  Drug:      %s", c['drug_name'])
        logger.info("  Gene:      %s (%s)", c['gene_name'], c['gene_id'])
        logger.info("  Category:  %s", c['gene_category'])
        logger.info("  Score:     %.2f/10", c['composite_score'])
        logger.info("    Target Similarity:     %s/10", c['target_similarity_score'])
        logger.info("    Pathway Proximity:     %.1f/10", c['final_proximity'])
        logger.info("    Mechanistic Rationale: %s/10", c['mechanistic_rationale_score'])
        logger.info("    Clinical Evidence:     %s/10", c['clinical_evidence_score'])
        logger.info("    Adverse Event Profile:  %s/10", c.get('adverse_event_score', c.get('safety_score', 'N/A')))
        logger.info("    Novelty Bonus:         %s/5", c['novelty_score'])
        logger.info("  Evidence:   %s", c['evidence_level'])
        logger.info("  Mechanism:  %s...", c['mechanism'][:150])
        logger.info("  Rationale:  %s...", c['rationale'][:180])
        logger.info("  Status:     %s", c['status'])


def print_gene_analysis(scored_candidates: list[CandidateDict], genes: dict[str, GeneDict], gene_id: str) -> None:
    """Log detailed analysis for a specific gene."""
    gene = genes.get(gene_id, {})
    gene_candidates = [c for c in scored_candidates if c["gene_id"] == gene_id]

    logger.info("=" * 75)
    logger.info("GENE-FOCUSED ANALYSIS: %s", gene.get('name', gene_id))
    logger.info("=" * 75)
    logger.info("  Function:        %s", gene.get('function', 'N/A'))
    logger.info("  Category:        %s", gene.get('category', 'N/A'))
    logger.info("  Chromosome:      %s", gene.get('chromosome', 'N/A'))
    logger.info("  Odds Ratio:      %s", gene.get('odds_ratio', 'N/A'))
    logger.info("  Lupus Evidence:  %s", (gene.get('lupus_evidence', 'N/A') or '')[:200])

    if not gene_candidates:
        logger.warning("  No repurposing candidates found for this gene.")
        return

    logger.info("  %d repurposing candidates:", len(gene_candidates))
    for i, c in enumerate(gene_candidates, 1):
        logger.info("    %d. %s | Score: %.2f | %s", i, c['drug_name'], c['composite_score'], c['tier'])
        logger.info("       Mechanism: %s...", c['mechanism'][:120])
        logger.info("       Rationale: %s...", c['rationale'][:150])
        logger.info("       Evidence:  %s", c['evidence_level'])
        logger.info("       Status:    %s", c['status'])


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

    logger.info("Loading %s knowledge graph...", args.disease.upper())
    G = load_knowledge_graph(args.disease)
    logger.info("Graph loaded: %d nodes, %d edges", G.number_of_nodes(), G.number_of_edges())

    logger.info("Loading gene and candidate data...")
    genes = load_genes(args.disease)
    candidates_data = load_json(DATA_DIR / "candidates.json")
    candidates = candidates_data["repurposing_candidates"]
    logger.info("Loaded %d genes, %d repurposing candidates", len(genes), len(candidates))

    logger.info("Identifying untargeted %s genes...", args.disease.upper())
    untargeted = identify_untargeted_genes(G)
    untargeted_ids = {g["id"] for g in untargeted}
    logger.info("Found %d untargeted genes:", len(untargeted))
    for g in untargeted:
        logger.info("  - %s (%s) -- %s", g['name'], g['id'], g.get('category', ''))

    logger.info("Scoring candidates...")
    scored = score_candidates(G, candidates, genes)

    scored = [c for c in scored if c["gene_id"] in untargeted_ids]
    logger.info("Scored %d candidates across %d genes", len(scored), len(set(c['gene_id'] for c in scored)))

    analyze(scored)

    if args.gene:
        print_gene_analysis(scored, genes, args.gene)
    else:
        print_top_candidates(scored, args.top)

    if args.export_html:
        from med_research.pipeline.drug_repurposing.report import generate_html_report
        generate_html_report(scored, untargeted, genes, G)
        logger.info("HTML report generated")

    return scored


if __name__ == "__main__":
    scored = main()
