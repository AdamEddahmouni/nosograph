"""Discover disease candidates from Open Targets + MONDO bulk data.

Output: data/candidates/disease_candidates.json

Usage:
    python scripts/collect_disease_candidates.py --limit 200
    python scripts/collect_disease_candidates.py --min-genes 5 --min-drugs 1
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from med_research.diseases.bulk_store import OpenTargetsBulkStore
from med_research.diseases.scaffold import load_disease_registry, sanitize_id

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "candidates" / "disease_candidates.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect disease candidates from OT bulk data")
    parser.add_argument("--limit", type=int, default=200, help="Max candidates to output")
    parser.add_argument("--min-genes", type=int, default=3, help="Minimum OT gene associations")
    parser.add_argument("--min-drugs", type=int, default=0, help="Minimum known drugs")
    parser.add_argument("--min-score", type=float, default=0.0, help="Minimum association score filter")
    args = parser.parse_args()

    store = OpenTargetsBulkStore()
    if not store.is_available():
        print("Bulk store not available. Run scripts/setup_opentargets_bulk.py first.")
        return 1

    registry_ids = {sanitize_id(d.get("id", "")) for d in load_disease_registry()}
    registry_efos = {
        d.get("efo_id") for d in load_disease_registry() if d.get("efo_id")
    }

    candidates = []
    for row in store.list_diseases(min_targets=args.min_genes, limit=50000):
        efo = row["efo_id"]
        if efo in registry_efos:
            continue
        if row["drug_count"] < args.min_drugs:
            continue
        slug = sanitize_id(row["name"])
        if slug in registry_ids:
            continue
        candidates.append(
            {
                "id": slug,
                "name": row["name"],
                "efo_id": efo,
                "mondo_id": None,
                "category": "",
                "gene_count": row["gene_count"],
                "drug_count": row["drug_count"],
                "confidence": min(1.0, row["gene_count"] / 20.0),
            }
        )

    candidates.sort(key=lambda c: (c["drug_count"], c["gene_count"]), reverse=True)
    candidates = candidates[:args.limit]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "total": len(candidates),
        "filters": {
            "min_genes": args.min_genes,
            "min_drugs": args.min_drugs,
            "min_score": args.min_score,
        },
        "candidates": candidates,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(candidates)} candidates to {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
