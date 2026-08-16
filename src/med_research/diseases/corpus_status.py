"""Corpus-wide metrics and batch status reporting."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from med_research.diseases.base import Disease
from med_research.diseases.registry_quality import is_blocked_slug
from med_research.diseases.tier_model import aggregate_tiers, compute_tier

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_STATUS_PATH = ROOT / "data" / "reports" / "disease_batch_status.json"
DEFAULT_BASELINE_PATH = ROOT / "data" / "reports" / "corpus_baseline.json"


def _entity_counts(disease_id: str) -> dict[str, int]:
    """Lightweight KG entity counts without full coverage report."""
    try:
        disease = Disease(disease_id)
        genes = disease.load_genes().get("genes", [])
        drugs = disease.load_drugs().get("drugs", [])
        pathways = disease.load_pathways().get("pathways", [])
        return {"genes": len(genes), "drugs": len(drugs), "pathways": len(pathways)}
    except Exception:
        return {"genes": 0, "drugs": 0, "pathways": 0}


def build_corpus_status(
    *,
    limit: Optional[int] = None,
    include_symptom_source: bool = False,
) -> dict[str, Any]:
    """Scan disease modules and produce tier + gap metrics."""
    disease_ids = sorted(Disease.list_all())
    if limit:
        disease_ids = disease_ids[:limit]

    per_disease: list[dict[str, Any]] = []
    symptoms_populated = 0

    for did in disease_ids:
        if is_blocked_slug(did):
            per_disease.append(
                {"disease_id": did, "tier": "blocked", "config_gaps": ["non_disease_slug"]}
            )
            continue
        try:
            disease = Disease(did)
            checks = disease.validate()
            counts = _entity_counts(did)
            drug_count = counts["drugs"]
            strict_pass = all(s == "ok" for s in checks.values())
            tier = compute_tier(did, checks, drug_count=drug_count, strict_pass=strict_pass)
            symptoms = disease.config.get("SYMPTOMS", [])
            symptom_count = len(symptoms) if isinstance(symptoms, list) else 0
            if symptom_count:
                symptoms_populated += 1
            row: dict[str, Any] = {
                "disease_id": did,
                "name": disease.profile.name,
                "tier": tier,
                "strict_pass": strict_pass,
                "gene_count": counts["genes"],
                "drug_count": drug_count,
                "pathway_count": counts["pathways"],
                "symptom_count": symptom_count,
                "config_gaps": [f for f, s in checks.items() if s != "ok"],
            }
            if include_symptom_source and symptom_count:
                row["symptom_source"] = "config"
            elif include_symptom_source:
                row["symptom_source"] = "none"
            per_disease.append(row)
        except Exception as exc:
            per_disease.append({"disease_id": did, "tier": "blocked", "error": str(exc)})

    aggregate = aggregate_tiers(per_disease)
    aggregate["total"] = len(per_disease)
    aggregate["symptoms_populated"] = symptoms_populated
    aggregate["L3_research_ready"] = aggregate.get("L3", 0)
    aggregate["L2_pipeline_ready"] = aggregate.get("L2", 0)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "aggregate": aggregate,
        "per_disease": per_disease,
    }


def write_corpus_baseline(
    path: Path = DEFAULT_BASELINE_PATH, *, limit: Optional[int] = None
) -> dict[str, Any]:
    """Write corpus baseline metrics."""
    status = build_corpus_status(limit=limit, include_symptom_source=False)
    baseline = {
        "generated_at": status["generated_at"],
        "metrics": status["aggregate"],
        "tier_counts": {
            k: v for k, v in status["aggregate"].items() if k in ("L0", "L1", "L2", "L3", "blocked")
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
    return baseline


def load_status_report(path: Path = DEFAULT_STATUS_PATH) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
