"""Resolve EFO/MONDO identifiers for registry diseases.

Default is dry-run; use --apply to update disease_registry.json.

Usage:
    python scripts/resolve_registry_ids.py
    python scripts/resolve_registry_ids.py --apply
    python scripts/resolve_registry_ids.py --apply --min-confidence 0.85
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from med_research.diseases.id_resolver import CONFIDENCE_THRESHOLD, DiseaseIdResolver

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "data" / "reports" / "id_resolution.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve disease EFO/MONDO identifiers")
    parser.add_argument("--apply", action="store_true", help="Update disease_registry.json")
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=CONFIDENCE_THRESHOLD,
        help="Minimum confidence for --apply",
    )
    parser.add_argument("--no-orphans", action="store_true", help="Skip filesystem orphan modules")
    args = parser.parse_args()

    resolver = DiseaseIdResolver()
    results = resolver.resolve_registry(include_orphans=not args.no_orphans)
    report = resolver.build_report(results)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Report: {REPORT_PATH}")
    print(
        f"Resolved: {report['resolved']}/{report['total']} "
        f"({report['resolution_rate']:.1%}), "
        f"ambiguous: {report['ambiguous']}, failed: {report['failed']}"
    )

    if args.apply:
        n = resolver.apply_to_registry(results, min_confidence=args.min_confidence)
        print(f"Applied {n} field updates to disease_registry.json")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
