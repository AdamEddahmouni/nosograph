"""Literature Mining, Virtual Screening, Clinical Trials, ML services."""

from typing import Any

from med_research.diseases.coverage import module_coverage
from med_research.exceptions import ModuleNotAvailableError
from med_research.web.config import USE_CACHE
from med_research.web.dependencies import get_candidates, get_kg_genes, safe_serialize
from med_research.web.services.registry_service import (
    dispatch_sync_module,
    make_progress_reporter,
    require_runnable_coverage,
)


def run_literature(
    max_articles: int = 30,
    targeted: bool = False,
    no_cache: bool = False,
    progress_callback: Any = None,
    disease_id: str = "sle",
) -> dict:
    """Run literature mining on PubMed via the literature_mining registry adapter."""
    genes = get_kg_genes(disease_id)
    candidates = get_candidates(disease_id)
    reporter = make_progress_reporter(progress_callback)

    reporter("Literature mining", 0, 4)

    raw = dispatch_sync_module(
        "literature_mining",
        disease_id,
        max_per_query=max_articles,
        use_cache=not no_cache and USE_CACHE,
        targeted_candidates=targeted,
        progress_callback=progress_callback,
    )
    crossref = raw.get("results", {})

    if not crossref or not crossref.get("article_matches"):
        reporter("Literature mining complete", 4, 4)
        coverage = module_coverage(
            disease_id, "literature", ("genes", "drugs", "pathways", "pubmed_queries")
        )
        return {
            "total_articles": 0,
            "queries_run": 0,
            "articles": [],
            "gene_coverage": [],
            "candidate_support": {},
            "coverage": coverage.to_dict(),
            "status": "ready",
        }

    article_matches = crossref["article_matches"]
    reporter("Building gene coverage profiles", 3, 4)

    raw_coverage = crossref.get("gene_coverage", {})
    gene_coverage = []
    for gene_id, cov_info in raw_coverage.items():
        if isinstance(cov_info, dict):
            gene_coverage.append(
                {
                    "gene_id": gene_id,
                    "gene_name": genes.get(gene_id, {}).get("name", gene_id),
                    "article_count": cov_info.get("articles", 0),
                    "supporting_count": cov_info.get("supporting_count", 0),
                    "coverage_score": cov_info.get("coverage_score", 0),
                }
            )
        elif isinstance(cov_info, (int, float)):
            gene_coverage.append(
                {
                    "gene_id": gene_id,
                    "gene_name": genes.get(gene_id, {}).get("name", gene_id),
                    "article_count": cov_info,
                    "supporting_count": cov_info,
                    "coverage_score": min(cov_info / max(len(article_matches), 1) * 100, 100),
                }
            )

    reporter("Literature mining complete", 4, 4)
    coverage = module_coverage(
        disease_id, "literature", ("genes", "drugs", "pathways", "pubmed_queries")
    )
    return {
        "total_articles": len(article_matches),
        "queries_run": 5 + (len(candidates) if targeted else 0),
        "articles": article_matches[:max_articles],
        "gene_coverage": gene_coverage,
        "candidate_support": crossref.get("candidate_support", {}),
        "coverage": coverage.to_dict(),
        "status": "limited_coverage" if coverage.level == "partial" else "ready",
    }


def run_screening(
    gene_id: str | None = None,
    top_n: int = 15,
    use_vina: bool = False,
    progress_callback: Any = None,
    disease_id: str = "sle",
) -> dict:
    """Run virtual drug screening via the virtual_screening registry adapter."""
    reporter = make_progress_reporter(progress_callback)
    coverage = module_coverage(
        disease_id,
        "screening",
        ("genes", "drugs", "pathways", "screening_profile"),
    )
    if not coverage.is_runnable:
        reporter("Screening blocked", 1, 1)
        require_runnable_coverage(coverage, "virtual_screening")

    reporter("Virtual screening", 0, 3)

    if gene_id:
        target_ids = [gene_id]
    else:
        untargeted = dispatch_sync_module(
            "virtual_screening",
            disease_id,
            operation="untargeted_genes",
        )
        target_ids = [g["id"] for g in untargeted.get("untargeted_genes", [])]

    results = dispatch_sync_module(
        "virtual_screening",
        disease_id,
        target_genes=target_ids,
        top_n=top_n,
        use_vina=use_vina,
        progress_callback=progress_callback,
    )

    coverage = results.get("coverage", coverage.to_dict())
    reporter("Formatting screening results", 2, 3)
    targets = []
    for gid, target_data in results.get("results_per_target", {}).items():
        top_compounds = []
        for c in target_data.get("top_compounds", []):
            top_compounds.append(
                {
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
                }
            )

        targets.append(
            {
                "gene_id": gid,
                "gene_name": target_data["gene_info"].get("name", gid),
                "gene_category": target_data["gene_info"].get("category", ""),
                "top_compounds": top_compounds,
                "total_screened": target_data["total_screened"],
                "mean_score": target_data["mean_score"],
            }
        )

    stats = results.get("stats", {})
    reporter("Virtual screening complete", 3, 3)
    return {
        "targets": targets,
        "compounds_screened": stats.get("compounds_screened", 0),
        "total_pairings": stats.get("total_pairings", 0),
        "tier1_count": stats.get("tier1_count", 0),
        "tier2_count": stats.get("tier2_count", 0),
        "vina_available": stats.get("vina_available", False),
        "rdkit_available": stats.get("rdkit_available", False),
        "coverage": coverage,
        "status": results.get("status", "ready"),
        "disease_id": results.get("disease_id", disease_id),
        "strategy_id": results.get("strategy_id", ""),
        "strategy_fingerprint": results.get("strategy_fingerprint", ""),
        "strategy_limitations": results.get("strategy_limitations", []),
    }


def run_trials(
    max_trials: int = 100,
    query: str = "lupus OR SLE",
    no_cache: bool = False,
    progress_callback: Any = None,
    disease_id: str = "sle",
) -> dict:
    """Track clinical trials via the clinical_trials registry adapter."""
    reporter = make_progress_reporter(progress_callback)

    if not query or query == "lupus OR SLE":
        try:
            from med_research.diseases.base import Disease

            query = Disease(disease_id).get_trial_query()
        except ValueError:
            query = "lupus OR SLE"

    reporter("Searching ClinicalTrials.gov", 0, 3)
    results = dispatch_sync_module(
        "clinical_trials",
        disease_id,
        query=query,
        max_results=max_trials,
        use_cache=not no_cache and USE_CACHE,
        progress_callback=progress_callback,
    )

    reporter("Processing trial data", 2, 3)
    trials = results.get("trials", [])
    stats = results.get("stats", {})
    kg_crossref = results.get("kg_crossref", {})

    moa_dist: dict[str, int] = {}
    for t in trials:
        moa = t.get("moa_category", "Other")
        moa_dist[moa] = moa_dist.get(moa, 0) + 1

    reporter("Clinical trials tracking complete", 3, 3)
    coverage = results.get("coverage", {})
    # The engine reports top sponsors as a {sponsor: count} dict already
    # limited to the top 10; the API contract is a list of dicts.
    top_sponsors = stats.get("top_sponsors", {})
    if isinstance(top_sponsors, dict):
        top_sponsors = [
            {"name": sponsor, "count": count} for sponsor, count in list(top_sponsors.items())[:10]
        ]
    else:
        top_sponsors = top_sponsors[:10] if isinstance(top_sponsors, list) else []
    return {
        "total_trials": len(trials),
        "phase_distribution": stats.get("phase_counts", {}),
        "moa_distribution": moa_dist,
        "top_sponsors": top_sponsors,
        "trials": trials[:max_trials],
        "kg_crossref": kg_crossref,
        "coverage": coverage,
        "status": results.get("status", "ready"),
    }


def run_ml_prediction(
    top_n: int = 15,
    no_shap: bool = False,
    progress_callback: Any = None,
    disease_id: str = "sle",
) -> dict:
    """Run ML target druggability prediction via the ml_predictor registry adapter."""
    coverage = module_coverage(disease_id, "ml_predictor", ("genes", "relationships"))
    if not coverage.is_runnable:
        require_runnable_coverage(coverage, "ml_predictor")

    reporter = make_progress_reporter(progress_callback)
    reporter("ML prediction", 0, 3)

    results = dispatch_sync_module(
        "ml_predictor",
        disease_id,
        top=top_n,
        progress_callback=progress_callback,
    )

    if results.get("error"):
        reporter("ML prediction failed", 3, 3)
        raise ModuleNotAvailableError(results["error"])

    reporter("Formatting predictions", 2, 3)
    predictions = safe_serialize(results.get("predictions", []))
    for i, p in enumerate(predictions[:top_n], 1):
        p["rank"] = i

    model_metrics = safe_serialize(results.get("model_metrics", {}))

    top_features = []
    importance = results.get("feature_importance", {})
    if importance:
        sorted_features = sorted(importance.items(), key=lambda x: float(x[1]), reverse=True)[:10]
        for name, imp in sorted_features:
            top_features.append({"feature": name, "importance": float(imp)})

    reporter("ML prediction complete", 3, 3)
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
        "coverage": coverage.to_dict(),
        "status": "limited_coverage" if coverage.level == "partial" else "ready",
    }
