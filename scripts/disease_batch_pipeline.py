"""Orchestrate the bulk disease harvest pipeline with quality gate reporting.

Usage:
    python scripts/disease_batch_pipeline.py --repair-all --workers 16
    python scripts/disease_batch_pipeline.py --collect --harvest --populate --symptoms --validate
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from med_research.diseases.base import Disease
from med_research.diseases.bulk_scaffold import bulk_harvest, print_bulk_harvest_summary
from med_research.diseases.coverage_report import build_coverage_report
from med_research.diseases.expression_proxy import apply_proxy_all
from med_research.diseases.symptom_harvester import harvest_all_symptoms
from med_research.pipeline.gene_expression.geo import CURATED_CONSENSUS_DISEASES

ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "data" / "reports" / "disease_batch_status.json"
SCRIPTS = ROOT / "scripts"


def _run_script(script: str, *args: str) -> int:
    cmd = [sys.executable, str(SCRIPTS / script), *args]
    print(f"\n>> {' '.join(cmd)}")
    return subprocess.call(cmd)


def _tier_for_disease(disease_id: str, strict_pass: bool) -> str:
    if disease_id in CURATED_CONSENSUS_DISEASES:
        return "L3"
    if strict_pass:
        return "L2"
    return "blocked"


def _ensure_ot_bulk_setup(*, from_fixtures: bool = False) -> int:
    """Ensure OT parquet is available; prefer an existing real store over fixtures."""
    from med_research.diseases.bulk_store import OpenTargetsBulkStore

    if OpenTargetsBulkStore().is_available():
        print("Open Targets bulk store already available; skipping setup")
        return 0
    if from_fixtures:
        return _run_script("setup_opentargets_bulk.py", "--from-fixtures")
    code = _run_script("setup_opentargets_bulk.py")
    if code != 0:
        print("Open Targets download incomplete; falling back to fixture subset")
        return _run_script("setup_opentargets_bulk.py", "--from-fixtures")
    return code


def main() -> int:
    parser = argparse.ArgumentParser(description="Bulk disease batch pipeline orchestrator")
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Ensure Open Targets bulk parquet is available (download or fixtures)",
    )
    parser.add_argument(
        "--fixtures",
        action="store_true",
        help="With --setup, use test fixtures instead of downloading OT parquet",
    )
    parser.add_argument("--resolve", action="store_true", help="Resolve registry IDs (--apply)")
    parser.add_argument("--collect", action="store_true", help="Collect disease candidates")
    parser.add_argument("--harvest", action="store_true", help="Bulk harvest from parquet")
    parser.add_argument("--repair-all", action="store_true", help="Re-harvest all registry diseases")
    parser.add_argument("--symptoms", action="store_true", help="Harvest symptoms into config.py")
    parser.add_argument("--populate", action="store_true", help="Populate disease configs")
    parser.add_argument("--expression-proxy", action="store_true", help="Register L2 expression proxies")
    parser.add_argument("--validate", action="store_true", help="Validate all diseases (strict)")
    parser.add_argument("--workers", type=int, default=8, help="Parallel harvest workers")
    parser.add_argument("--limit", type=int, help="Limit diseases per step")
    args = parser.parse_args()

    # Default: run full repair pipeline when no flags given
    if not any(
        [
            args.setup,
            args.resolve,
            args.collect,
            args.harvest,
            args.repair_all,
            args.symptoms,
            args.populate,
            args.expression_proxy,
            args.validate,
        ]
    ):
        args.setup = True
        args.resolve = True
        args.harvest = True
        args.symptoms = True
        args.populate = True
        args.expression_proxy = True
        args.validate = True

    if args.setup:
        code = _ensure_ot_bulk_setup(from_fixtures=args.fixtures)
        if code != 0:
            return code

    if args.resolve:
        code = _run_script("resolve_registry_ids.py", "--apply")
        if code != 0:
            return code

    if args.collect:
        collect_args = ["--limit", str(args.limit or 200)]
        code = _run_script("collect_disease_candidates.py", *collect_args)
        if code != 0:
            return code

    harvest_report = None
    if args.harvest or args.repair_all:
        try:
            harvest_report = bulk_harvest(
                repair=args.repair_all,
                workers=args.workers,
                limit=args.limit,
                use_gwas=False,
            )
            print_bulk_harvest_summary(harvest_report)
        except FileNotFoundError as exc:
            print(f"Harvest skipped: {exc}")
            return 1

    if args.symptoms:
        harvest_all_symptoms(write=True, limit=args.limit)

    if args.populate:
        populate_args = ["--all", "--write"]
        code = _run_script("populate_disease_configs.py", *populate_args)
        if code != 0:
            print("populate_disease_configs returned non-zero (continuing)")

    if args.expression_proxy:
        proxy_report = apply_proxy_all(limit=args.limit)
        print(f"Expression proxy: registered {proxy_report['registered']}/{proxy_report['total']}")

    per_disease = []
    l3, l2, blocked = 0, 0, 0
    if args.validate:
        for did in sorted(Disease.list_all()):
            try:
                disease = Disease(did)
                checks = disease.validate()
                strict_pass = all(s == "ok" for s in checks.values())
                coverage = build_coverage_report(did)
                tier = _tier_for_disease(did, strict_pass)
                if tier == "L3":
                    l3 += 1
                elif tier == "L2":
                    l2 += 1
                else:
                    blocked += 1
                symptoms = disease.config.get("SYMPTOMS", [])
                per_disease.append(
                    {
                        "disease_id": did,
                        "name": disease.profile.name,
                        "tier": tier,
                        "strict_pass": strict_pass,
                        "gene_count": coverage["entity_counts"]["genes"],
                        "drug_count": coverage["entity_counts"]["drugs"],
                        "pathway_count": coverage["entity_counts"]["pathways"],
                        "symptom_count": len(symptoms) if isinstance(symptoms, list) else 0,
                        "config_gaps": [f for f, s in checks.items() if s != "ok"],
                    }
                )
            except Exception as exc:
                blocked += 1
                per_disease.append({"disease_id": did, "tier": "blocked", "error": str(exc)})

    status = {
        "harvest": harvest_report,
        "aggregate": {
            "L3_research_ready": l3,
            "L2_pipeline_ready": l2,
            "blocked": blocked,
            "total": len(per_disease),
        },
        "per_disease": per_disease,
    }
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(status, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"\nStatus report: {STATUS_PATH}")
    print(f"  L3 (research-ready): {l3}")
    print(f"  L2 (pipeline-ready): {l2}")
    print(f"  Blocked: {blocked}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
