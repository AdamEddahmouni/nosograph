"""Merge reviewed disease candidates into the registry.

Usage:
    python scripts/merge_disease_candidates.py --dry-run
    python scripts/merge_disease_candidates.py --apply --limit 50
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from med_research.diseases.registry_quality import filter_disease_entries, is_disease_like_entry
from med_research.diseases.scaffold import load_disease_registry, sanitize_id, save_disease_registry

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES_PATH = ROOT / "data" / "candidates" / "disease_candidates.json"

_THERAPEUTIC_AREAS = {
    "cancer": "oncology",
    "neoplasm": "oncology",
    "cardiovascular": "cardiovascular",
    "immune": "autoimmune",
    "infectious": "infectious",
    "metabolic": "metabolic",
    "neuro": "neurology",
    "psychiatric": "psychiatry",
}


def _infer_category(name: str, therapeutic_areas: list[str] | None = None) -> str:
    if therapeutic_areas:
        for area in therapeutic_areas:
            lowered = area.lower()
            for key, category in _THERAPEUTIC_AREAS.items():
                if key in lowered:
                    return category
    lowered = name.lower()
    for key, category in _THERAPEUTIC_AREAS.items():
        if key in lowered:
            return category
    return "other"


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge disease candidates into registry")
    parser.add_argument("--apply", action="store_true", help="Write merged registry")
    parser.add_argument("--dry-run", action="store_true", help="Preview merge only")
    parser.add_argument("--limit", type=int, default=100, help="Max candidates to merge")
    args = parser.parse_args()

    if not CANDIDATES_PATH.is_file():
        print(f"No candidates file at {CANDIDATES_PATH}")
        return 1

    payload = json.loads(CANDIDATES_PATH.read_text(encoding="utf-8"))
    candidates = payload.get("candidates", [])[: args.limit]
    registry = load_disease_registry()
    existing_ids = {sanitize_id(e.get("id", "")) for e in registry}
    existing_efos = {e.get("efo_id") for e in registry if e.get("efo_id")}

    merged = []
    for cand in candidates:
        if not is_disease_like_entry(cand):
            continue
        did = sanitize_id(cand.get("id", ""))
        efo = cand.get("efo_id")
        if did in existing_ids or efo in existing_efos:
            continue
        entry = {
            "id": did,
            "name": cand.get("name", did),
            "category": cand.get("category") or _infer_category(cand.get("name", "")),
            "efo_id": efo,
            "mondo_id": cand.get("mondo_id"),
            "resolution_confidence": cand.get("confidence", 0.8),
            "resolution_source": "candidate_merge",
        }
        merged.append(entry)

    filtered, rejected = filter_disease_entries(merged)
    print(f"Candidates reviewed: {len(candidates)}")
    print(f"Would merge: {len(filtered)} (rejected {len(rejected)})")

    if args.apply and not args.dry_run:
        registry.extend(filtered)
        save_disease_registry(registry)
        print(f"Registry now has {len(registry)} entries")
    elif args.dry_run or not args.apply:
        for entry in filtered[:10]:
            print(f"  + {entry['id']}: {entry['name']} ({entry.get('efo_id')})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
