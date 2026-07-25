"""Literature Mining, Virtual Screening, Clinical Trials, ML services."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from web_api.config import (
    USE_CACHE,
)
from web_api.dependencies import get_candidates, get_kg_genes, get_knowledge_graph, safe_serialize

# ── Literature Mining ──────────────────────────────────────────────────────

def run_literature(
    max_articles: int = 30,
    targeted: bool = False,
    no_cache: bool = False,
    progress_callback=None,
) -> dict:
    """Run literature mining on PubMed using the mine_literature pipeline."""
    from literature_mining.crossref import cross_reference_articles
    from literature_mining.miner import mine_literature

    genes = get_kg_genes()
    candidates = get_candidates()
    cb = progress_callback or (lambda p, m: None)

    cb(10, "Loading knowledge graph entities…")

    cb(20, "Mining PubMed for SLE-related articles…")
    articles, entities, _ = mine_literature(
        max_per_query=max_articles,
        use_cache=not no_cache and USE_CACHE,
        targeted_candidates=targeted,
    )

    if not articles:
        cb(100, "Literature mining complete — no articles found")
        return {
            "total_articles": 0,
            "queries_run": 0,
            "articles": [],
            "gene_coverage": [],
            "candidate_support": [],
        }

    cb(50, f"Cross-referencing {len(articles)} articles with knowledge graph…")
    crossref = cross_reference_articles(articles, entities, candidates)

    cb(75, "Building gene coverage profiles…")
    # gene_coverage from crossref is a dict keyed by gene_id
    raw_coverage = crossref.get("gene_coverage", {})
    gene_coverage = []
    for gene_id, cov_info in raw_coverage.items():
        if isinstance(cov_info, dict):
            gene_coverage.append({
                "gene_id": gene_id,
                "gene_name": genes.get(gene_id, {}).get("name", gene_id),
                "article_count": cov_info.get("article_count", 0),
                "supporting_count": cov_info.get("supporting_count", 0),
                "coverage_score": cov_info.get("coverage_score", 0),
            })
        elif isinstance(cov_info, (int, float)):
            gene_coverage.append({
                "gene_id": gene_id,
                "gene_name": genes.get(gene_id, {}).get("name", gene_id),
                "article_count": cov_info,
                "supporting_count": cov_info,
                "coverage_score": min(cov_info / max(len(articles), 1) * 100, 100),
            })

    cb(100, "Literature mining complete")
    return {
        "total_articles": len(articles),
        "queries_run": 5 + (len(candidates) if targeted else 0),
        "articles": articles[:max_articles],
        "gene_coverage": gene_coverage,
        "candidate_support": crossref.get("candidate_support", []),
    }


# ── Virtual Screening ──────────────────────────────────────────────────────

def run_screening(
    gene_id: str | None = None,
    top_n: int = 15,
    use_vina: bool = False,
    progress_callback=None,
) -> dict:
    """Run virtual drug screening."""
    from virtual_screening.screening import (
        build_compound_library,
        get_untargeted_genes,
        screen_compounds,
    )

    cb = progress_callback or (lambda p, m: None)

    cb(10, "Building compound library…")
    library = build_compound_library()

    cb(25, "Selecting target genes…")
    target_ids = [gene_id] if gene_id else [g["id"] for g in get_untargeted_genes()]

    cb(35, f"Screening {len(library)} compounds against {len(target_ids)} targets…")
    results = screen_compounds(
        target_genes=target_ids,
        compound_library=library,
        top_n=top_n,
        use_vina=use_vina,
    )

    cb(75, "Formatting screening results…")
    targets = []
    for gid, target_data in results.get("results_per_target", {}).items():
        top_compounds = []
        for c in target_data.get("top_compounds", []):
            top_compounds.append({
                "drug_id": c["id"],
                "drug_name": c["name"],
                "composite_score": c["composite_score"],
                "binding_estimate": c["binding_estimate"],
                "druglikeness": c["druglikeness"],
                "target_complementarity": c["target_complementarity"],
                "similarity_score": c["similarity_score"],
                "novelty_score": c["novelty_score"],
                "tier": c.get("tier", ""),
                "gene_id": c.get("gene_id", gid),
                "gene_name": c.get("gene_name", ""),
                "drug_type": c.get("type", ""),
            })

        targets.append({
            "gene_id": gid,
            "gene_name": target_data["gene_info"].get("name", gid),
            "gene_category": target_data["gene_info"].get("category", ""),
            "top_compounds": top_compounds,
            "total_screened": target_data["total_screened"],
            "mean_score": target_data["mean_score"],
        })

    stats = results.get("stats", {})

    cb(100, "Virtual screening complete")
    return {
        "targets": targets,
        "compounds_screened": stats.get("compounds_screened", 0),
        "total_pairings": stats.get("total_pairings", 0),
        "tier1_count": stats.get("tier1_count", 0),
        "tier2_count": stats.get("tier2_count", 0),
        "vina_available": stats.get("vina_available", False),
        "rdkit_available": stats.get("rdkit_available", False),
    }


# ── Clinical Trials ────────────────────────────────────────────────────────

def run_trials(
    max_trials: int = 100,
    query: str = "lupus OR SLE",
    no_cache: bool = False,
    progress_callback=None,
) -> dict:
    """Track clinical trials from ClinicalTrials.gov using the track_trials pipeline."""
    from clinical_trials.tracker import track_trials

    cb = progress_callback or (lambda p, m: None)

    cb(15, "Searching ClinicalTrials.gov…")
    results = track_trials(
        query=query,
        max_results=max_trials,
        use_cache=not no_cache and USE_CACHE,
    )

    cb(60, "Processing trial data…")
    trials = results.get("trials", [])
    stats = results.get("stats", {})
    kg_crossref = results.get("kg_crossref", {})

    # Build MoA distribution from categorized trials
    cb(85, "Computing mechanism-of-action distributions…")
    moa_dist = {}
    for t in trials:
        moa = t.get("moa_category", "Other")
        moa_dist[moa] = moa_dist.get(moa, 0) + 1

    cb(100, "Clinical trials tracking complete")
    return {
        "total_trials": len(trials),
        "phase_distribution": stats.get("phase_counts", {}),
        "moa_distribution": moa_dist,
        "top_sponsors": stats.get("top_sponsors", [])[:10],
        "trials": trials[:max_trials],
        "kg_crossref": kg_crossref,
    }


# ── ML Predictor ───────────────────────────────────────────────────────────

def run_ml_prediction(
    top_n: int = 15,
    no_shap: bool = False,
    progress_callback=None,
) -> dict:
    """Run ML target druggability prediction using train_and_predict."""
    from ml_predictor.predictor import train_and_predict

    cb = progress_callback or (lambda p, m: None)

    cb(10, "Loading knowledge graph…")
    G = get_knowledge_graph()

    cb(25, "Training XGBoost model and computing SHAP values…")
    results = train_and_predict(G, top_n=top_n)

    if "error" in results:
        cb(100, "ML prediction failed — see error details")
        return {
            "predictions": [],
            "model_type": "XGBoost",
            "error": results["error"],
            "top_features": [],
        }

    cb(70, "Formatting predictions and feature importance…")
    # Convert numpy types to native Python for JSON serialization
    predictions = safe_serialize(results.get("predictions", []))
    for i, p in enumerate(predictions[:top_n], 1):
        p["rank"] = i

    # model_metrics is a sub-dict inside results
    model_metrics = safe_serialize(results.get("model_metrics", {}))

    top_features = []
    importance = results.get("feature_importance", {})
    if importance:
        sorted_features = sorted(importance.items(), key=lambda x: float(x[1]), reverse=True)[:10]
        for name, imp in sorted_features:
            top_features.append({"feature": name, "importance": float(imp)})

    cb(100, "ML prediction complete")
    return {
        "predictions": predictions[:top_n],
        "model_type": "XGBoost",
        "cross_val_auc": (
            float(model_metrics.get("cv_auc_mean", 0))
            if model_metrics.get("cv_auc_mean") is not None
            else None
        ),
        "accuracy": (
            float(model_metrics.get("accuracy", 0))
            if model_metrics.get("accuracy") is not None
            else None
        ),
        "top_features": top_features,
    }
