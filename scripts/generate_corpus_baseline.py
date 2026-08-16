"""Generate corpus baseline metrics report.

Usage:
    python scripts/generate_corpus_baseline.py
    python scripts/generate_corpus_baseline.py --output data/reports/corpus_baseline.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from med_research.diseases.corpus_status import DEFAULT_BASELINE_PATH, write_corpus_baseline


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate corpus baseline metrics")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_BASELINE_PATH,
        help="Output JSON path",
    )
    parser.add_argument("--limit", type=int, help="Limit diseases scanned (default: all)")
    args = parser.parse_args()
    baseline = write_corpus_baseline(args.output, limit=args.limit)
    print(json.dumps(baseline, indent=2))
    print(f"\nWrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
