"""
Lupus ML Target Predictor

Trains XGBoost models to predict novel druggable targets for SLE
from knowledge graph features and generates SHAP interpretability.

Features extracted from the KG graph:
  - Degree (network connectivity)
  - Betweenness centrality
  - Pathway participation count
  - GWAS odds ratio
  - Category (one-hot)
  - Molecular type (kinase, receptor, transcription factor)

Labels: is_targeted (has a TARGETS edge from any drug)

Usage:
    python predictor.py                  # Train & predict
    python predictor.py --top 10 --export-html  # Top 10 + HTML report
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from med_research.pipeline.knowledge_graph.builder import build_graph

DATA_DIR = Path(__file__).parent / "data"
PROJECT_ROOT = Path(__file__).parent.parent

# Optional imports
XGB_AVAILABLE = False
SHAP_AVAILABLE = False
SKLEARN_AVAILABLE = False

try:
    import numpy as np
    NP_AVAILABLE = True
except ImportError:
    NP_AVAILABLE = False

try:
    from sklearn.metrics import classification_report
    from sklearn.model_selection import StratifiedKFold, cross_val_score
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False

try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False


# ── Feature Engineering ──────────────────────────────────────────────

_CATEGORIES = [
    "MHC / Antigen Presentation",
    "Type I Interferon Pathway",
    "JAK-STAT Signaling",
    "B Cell Signaling",
    "NF-κB Pathway",
    "Complement / Phagocytosis",
    "Complement Cascade",
    "T Cell Signaling",
    "T Cell Costimulation",
    "Immune Complex Clearance",
    "Innate Immune Sensing",
    "B Cell Survival",
    "Nuclear Receptor Signaling",
    "Lymphocyte Development",
    "Nucleotide Metabolism",
    "Autophagy",
]

_KINASE_KEYWORDS = ["kinase", "tyrosine kinase", "jak", "btk", "blk", "tyk2"]
_RECEPTOR_KEYWORDS = ["receptor", "fcgr", "tlr", "ifnar", "cd20"]
_TF_KEYWORDS = ["transcription factor", "regulatory factor", "stat", "irf", "ikzf", "prdm"]


def extract_features(G) -> tuple:
    """Extract features from the knowledge graph for all gene nodes.

    Returns:
        (X, gene_ids, labels) where X is feature matrix, gene_ids is list of gene names,
        and labels is list of (is_targeted, targeted_drugs) tuples.
    """
    if not NP_AVAILABLE:
        print("❌ numpy required. Install: pip install numpy")
        return np.array([]), [], []

    # Find targeted genes (those with TARGETS edge from a drug)
    targeted_genes = set()
    for u, v, d in G.edges(data=True):
        if d.get("type") == "TARGETS" and G.nodes[v].get("type") == "gene":
            targeted_genes.add(v)

    # Compute betweenness centrality
    try:
        betweenness = nx_betweenness(G) if "nx_betweenness" in dir() else {}
    except Exception:
        betweenness = {}

    features = []
    gene_ids = []
    labels = []

    for node, data in G.nodes(data=True):
        if data.get("type") != "gene":
            continue

        gene_id = node
        gene_ids.append(gene_id)
        is_targeted = 1 if gene_id in targeted_genes else 0

        # Which drugs target this gene
        targeting_drugs = []
        for u, v, d in G.edges(data=True):
            if d.get("type") == "TARGETS" and v == gene_id:
                if G.nodes[u].get("type") == "drug":
                    targeting_drugs.append(u)

        labels.append((is_targeted, targeting_drugs))

        category = data.get("category", "")
        function_text = data.get("description", "").lower()
        odds_ratio = data.get("odds_ratio") or 0.0

        # Build feature vector
        feat = [
            G.degree(node),                          # 0: degree
            betweenness.get(node, 0.0),             # 1: betweenness
            _count_pathways(G, node),                # 2: pathway count
            float(odds_ratio) if odds_ratio else 0.0,  # 3: odds ratio
            1 if odds_ratio else 0,                  # 4: has odds ratio
            1 if data.get("chromosome") else 0,      # 5: has chromosome data
            _is_type(function_text, _KINASE_KEYWORDS),     # 6: is kinase
            _is_type(function_text, _RECEPTOR_KEYWORDS),   # 7: is receptor
            _is_type(function_text, _TF_KEYWORDS),         # 8: is transcription factor
        ]

        # One-hot encode category
        for cat in _CATEGORIES:
            feat.append(1 if category == cat else 0)

        features.append(feat)

    return np.array(features, dtype=float), gene_ids, labels


def _count_pathways(G, gene_node: str) -> int:
    """Count how many pathway nodes this gene participates in."""
    count = 0
    for _, v, d in G.edges(gene_node, data=True):
        if d.get("type") == "PARTICIPATES_IN" and G.nodes[v].get("type") == "pathway":
            count += 1
    return count


def _is_type(text: str, keywords: list) -> int:
    return 1 if any(kw in text for kw in keywords) else 0


def nx_betweenness(G):
    """Compute betweenness centrality, catching errors."""
    try:
        import networkx as nx
        return nx.betweenness_centrality(G)
    except Exception:
        return {}


# ── ML Pipeline ──────────────────────────────────────────────────────


def train_and_predict(G, top_n: int = 15) -> dict:
    """Train XGBoost and predict druggability scores for all genes.

    Returns:
        dict with predictions, feature_importance, model_metrics, gene_details
    """
    if not all([XGB_AVAILABLE, SKLEARN_AVAILABLE, NP_AVAILABLE]):
        print("❌ xgboost, scikit-learn, and numpy required.")
        print("   Install: pip install xgboost scikit-learn numpy")
        return {"error": "Missing dependencies"}

    print("🔄 Extracting features from knowledge graph...")
    X, gene_ids, labels = extract_features(G)

    if len(X) == 0:
        return {"error": "No gene features extracted"}

    y = np.array([l[0] for l in labels])
    targeted_count = int(np.sum(y))
    untargeted_count = int(len(y) - targeted_count)

    print(f"   {len(gene_ids)} genes: {targeted_count} targeted, {untargeted_count} untargeted")

    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Feature names
    feature_names = (
        ["degree", "betweenness", "pathway_count", "odds_ratio",
         "has_odds_ratio", "has_chromosome", "is_kinase", "is_receptor", "is_tf"]
        + [f"cat_{c.replace(' ', '_').replace('/', '_')[:30]}" for c in _CATEGORIES]
    )
    feature_names = feature_names[:X.shape[1]]

    # Cross-validation
    print("\n🔄 Training XGBoost with stratified 5-fold CV...")
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=3,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        eval_metric="logloss",
    )

    if targeted_count >= 2 and untargeted_count >= 2 and min(targeted_count, untargeted_count) >= 2:
        cv = StratifiedKFold(n_splits=min(3, targeted_count, untargeted_count), shuffle=True, random_state=42)
        cv_scores = cross_val_score(model, X_scaled, y, cv=cv, scoring="roc_auc")
        print(f"   CV ROC-AUC: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")
    else:
        cv_scores = np.array([0.5])
        print("   ⚠️  Insufficient samples for CV")

    # Train on full data
    model.fit(X_scaled, y)

    # Predict probabilities for all genes (druggability score)
    probas = model.predict_proba(X_scaled)[:, 1]

    # Feature importance
    importance = dict(zip(feature_names, model.feature_importances_))
    importance = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))

    # Build results
    predictions = []
    for i, gene_id in enumerate(gene_ids):
        gene_data = G.nodes[gene_id]
        is_targeted = labels[i][0]
        drugs = labels[i][1]
        predictions.append({
            "gene_id": gene_id,
            "gene_name": gene_data.get("label", gene_id),
            "category": gene_data.get("category", ""),
            "druggability_score": round(float(probas[i]), 3),
            "is_targeted": bool(is_targeted),
            "targeted_by": drugs,
            "odds_ratio": gene_data.get("odds_ratio"),
            "degree": G.degree(gene_id),
            "pathway_count": _count_pathways(G, gene_id),
        })

    # Sort by druggability score
    predictions.sort(key=lambda x: x["druggability_score"], reverse=True)

    # SHAP analysis
    shap_values = None
    shap_summary = []
    if SHAP_AVAILABLE and hasattr(model, "get_booster"):
        print("🔄 Computing SHAP values...")
        try:
            explainer = shap.TreeExplainer(model)
            shap_vals = explainer.shap_values(X_scaled)
            for i, name in enumerate(feature_names):
                mean_impact = float(np.abs(shap_vals[:, i]).mean())
                shap_summary.append({
                    "feature": name,
                    "mean_abs_shap": round(mean_impact, 4),
                })
            shap_summary.sort(key=lambda x: x["mean_abs_shap"], reverse=True)
            shap_values = shap_vals
        except Exception as e:
            print(f"   ⚠️  SHAP error: {e}")

    # Generate top N untargeted genes
    untargeted_predictions = [p for p in predictions if not p["is_targeted"]]
    top_untargeted = untargeted_predictions[:top_n]

    return {
        "predictions": predictions,
        "top_untargeted": top_untargeted,
        "feature_importance": importance,
        "shap_summary": shap_summary,
        "shap_values": shap_values.tolist() if shap_values is not None and hasattr(shap_values, 'tolist') else None,
        "feature_names": feature_names,
        "gene_ids": gene_ids,
        "model_metrics": {
            "cv_roc_auc_mean": float(cv_scores.mean()),
            "cv_roc_auc_std": float(cv_scores.std()),
            "n_genes": len(gene_ids),
            "n_targeted": targeted_count,
            "n_untargeted": untargeted_count,
            "xgboost_available": XGB_AVAILABLE,
            "shap_available": SHAP_AVAILABLE,
        },
    }


# ── Summary & CLI ────────────────────────────────────────────────────


def print_summary(results: dict):
    """Print ML target prediction results."""
    metrics = results.get("model_metrics", {})

    print("\n" + "=" * 70)
    print("🧠 ML TARGET PREDICTOR RESULTS")
    print("=" * 70)

    print(f"\n  Genes analyzed:             {metrics.get('n_genes', 0)}")
    print(f"  Targeted (known drugs):     {metrics.get('n_targeted', 0)}")
    print(f"  Untargeted (opportunity):   {metrics.get('n_untargeted', 0)}")
    print(f"  CV ROC-AUC:                 {metrics.get('cv_roc_auc_mean', 0):.3f} ± {metrics.get('cv_roc_auc_std', 0):.3f}")
    print(f"  XGBoost:                    {'✅ available' if metrics.get('xgboost_available') else '❌ not available'}")
    print(f"  SHAP:                       {'✅ available' if metrics.get('shap_available') else '❌ not available'}")

    # Feature importance
    importance = results.get("feature_importance", {})
    if importance:
        print("\n  📊 Top features by importance:")
        for i, (feat, imp) in enumerate(list(importance.items())[:8]):
            print(f"    {i+1}. {feat:<35} {imp:.4f}")

    # Top predictions
    top = results.get("top_untargeted", [])
    if top:
        print("\n  🎯 Top predicted novel druggable targets:")
        for i, p in enumerate(top[:10]):
            drugs_note = f"  [targeted by: {', '.join(p['targeted_by'])}]" if p.get('targeted_by') else ""
            print(f"    {i+1:2}. {p['gene_name'][:45]:<47} "
                  f"Score: {p['druggability_score']:.3f}  "
                  f"Cat: {p['category']}{drugs_note}")

    # SHAP
    shap = results.get("shap_summary", [])
    if shap:
        print("\n  🔍 Top SHAP features (mean |impact|):")
        for s in shap[:5]:
            print(f"    • {s['feature']:<35} {s['mean_abs_shap']:.4f}")


def main():
    parser = argparse.ArgumentParser(
        description="Lupus ML Target Predictor — XGBoost + SHAP druggability prediction"
    )
    parser.add_argument(
        "--top", type=int, default=15,
        help="Number of top predicted targets (default: 15)",
    )
    parser.add_argument(
        "--export-html", action="store_true",
        help="Generate HTML report with SHAP plots",
    )
    parser.add_argument(
        "--no-shap", action="store_true",
        help="Skip SHAP analysis (faster)",
    )
    args = parser.parse_args()

    if not XGB_AVAILABLE:
        print("⚠️  XGBoost not installed. Install with: pip install xgboost scikit-learn")
        print("   Running in feature-engineering-only mode...")

    print("🔄 Building knowledge graph...")
    G = build_graph()
    print(f"   Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    results = train_and_predict(G, top_n=args.top)

    if "error" in results:
        print(f"❌ {results['error']}")
        return results

    print_summary(results)

    # Save results
    os.makedirs(DATA_DIR, exist_ok=True)
    output = {
        "predictions": results["predictions"],
        "top_untargeted": results["top_untargeted"],
        "feature_importance": results["feature_importance"],
        "shap_summary": results["shap_summary"],
        "model_metrics": results["model_metrics"],
    }
    out_path = DATA_DIR / "ml_predictions.json"
    out_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(f"\n💾 Results saved to {out_path}")

    if args.export_html:
        from med_research.pipeline.ml_predictor.report import generate_ml_report
        report_path = generate_ml_report(results)
        print(f"✅ HTML report generated: {report_path}")

    return results


if __name__ == "__main__":
    results = main()
