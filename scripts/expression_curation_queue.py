"""Rank diseases for manual expression consensus curation (L3 tier).

Usage:
    python scripts/expression_curation_queue.py --limit 50
    python scripts/expression_curation_queue.py --json data/reports/expression_queue.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from med_research.diseases.scaffold import _diseases_root, load_disease_registry, sanitize_id
from med_research.pipeline.gene_expression.geo import CURATED_CONSENSUS_DISEASES

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "reports" / "expression_curation_queue.json"

CATEGORY_PRIORITY = {
    "autoimmune": 10,
    "oncology": 9,
    "neurology": 8,
    "cardiovascular": 7,
    "metabolic": 6,
    "rare": 5,
}


def _entity_counts(disease_id: str) -> dict:
    root = _diseases_root() / disease_id / "data"
    counts = {"genes": 0, "drugs": 0, "pathways": 0}
    for key, fname in (("genes", "genes.json"), ("drugs", "drugs.json"), ("pathways", "pathways.json")):
        path = root / fname
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                counts[key] = len(data.get(key, []))
            except (json.JSONDecodeError, OSError):
                pass
    return counts


def _score_entry(entry: dict) -> float:
    did = sanitize_id(entry.get("id", ""))
    if did in CURATED_CONSENSUS_DISEASES:
        return -1.0
    category = (entry.get("category") or "").lower()
    cat_score = CATEGORY_PRIORITY.get(category, 3)
    counts = _entity_counts(did)
    return (
        cat_score * 10
        + counts["genes"] * 0.5
        + counts["drugs"] * 0.3
        + (1 if not counts["genes"] else 0)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build expression curation priority queue")
    parser.add_argument("--limit", type=int, default=50, help="Top N diseases to queue")
    parser.add_argument("--json", type=Path, default=DEFAULT_OUTPUT, help="Output JSON path")
    args = parser.parse_args()

    entries = load_disease_registry()
    ranked = sorted(entries, key=_score_entry, reverse=True)
    queue = []
    for entry in ranked[:args.limit]:
        did = sanitize_id(entry.get("id", ""))
        counts = _entity_counts(did)
        tier = "L3" if did in CURATED_CONSENSUS_DISEASES else "L2"
        queue.append(
            {
                "disease_id": did,
                "name": entry.get("name") or did,
                "category": entry.get("category") or "",
                "tier": tier,
                "priority_score": round(_score_entry(entry), 2),
                "gene_count": counts["genes"],
                "drug_count": counts["drugs"],
                "needs_curation": did not in CURATED_CONSENSUS_DISEASES,
            }
        )

    payload = {"limit": args.limit, "queue": queue}
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(queue)} entries to {args.json}")
    for item in queue[:10]:
        print(f"  {item['priority_score']:6.1f}  {item['disease_id']}  ({item['tier']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
