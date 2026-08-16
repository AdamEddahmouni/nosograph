"""Review and apply ID resolution corrections.

Usage:
    python scripts/review_id_resolution.py --export review_queue.csv
    python scripts/review_id_resolution.py --apply-corrections corrections.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from med_research.diseases.id_resolver import DiseaseIdResolver
from med_research.diseases.scaffold import load_disease_registry, sanitize_id, save_disease_registry

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "data" / "reports" / "id_resolution.json"


def _load_report() -> dict:
    if not REPORT_PATH.is_file():
        resolver = DiseaseIdResolver()
        report = resolver.resolve_registry(include_orphans=True)
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return report
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


def export_queue(path: Path) -> int:
    report = _load_report()
    rows = report.get("needs_review") or report.get("ambiguous") or []
    if not rows:
        for entry in report.get("entries", []):
            if entry.get("needs_review") or entry.get("resolution_source") == "fuzzy":
                rows.append(entry)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "disease_id",
                "name",
                "efo_id",
                "mondo_id",
                "resolution_confidence",
                "resolution_source",
                "notes",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "disease_id": row.get("disease_id", ""),
                    "name": row.get("name", ""),
                    "efo_id": row.get("efo_id", ""),
                    "mondo_id": row.get("mondo_id", ""),
                    "resolution_confidence": row.get("resolution_confidence", ""),
                    "resolution_source": row.get("resolution_source", ""),
                    "notes": "; ".join(row.get("notes") or []),
                }
            )
    print(f"Exported {len(rows)} review rows to {path}")
    return 0


def apply_corrections(path: Path) -> int:
    corrections = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(corrections, list):
        corrections = corrections.get("corrections", [])

    registry = load_disease_registry()
    by_id = {sanitize_id(e.get("id", "")): e for e in registry}
    applied = 0
    for item in corrections:
        did = sanitize_id(item.get("disease_id", ""))
        if did not in by_id:
            continue
        entry = by_id[did]
        for key in ("efo_id", "mondo_id", "name", "category"):
            if key in item and item[key]:
                entry[key] = item[key]
        if "resolution_confidence" in item:
            entry["resolution_confidence"] = item["resolution_confidence"]
        if "resolution_source" in item:
            entry["resolution_source"] = item["resolution_source"]
        applied += 1

    save_disease_registry(registry)
    print(f"Applied {applied} corrections to disease_registry.json")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Review ID resolution queue")
    parser.add_argument("--export", type=Path, help="Export review queue CSV")
    parser.add_argument("--apply-corrections", type=Path, help="Apply corrections JSON")
    args = parser.parse_args()

    if args.export:
        return export_queue(args.export)
    if args.apply_corrections:
        return apply_corrections(args.apply_corrections)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
