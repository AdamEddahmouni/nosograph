"""Admit on-disk disease-like modules into disease_registry.json.

The harvest JSON is an Open Targets catalog, not Disease.list_all(). Curated
short-slug packages were skipped by batch_scaffold because their directories
already existed. This script is the generator/process fix — it does not
hand-edit individual rows.

  python scripts/reconcile_harvest_registry.py          # apply
  python scripts/reconcile_harvest_registry.py --check  # CI (exit 1 on drift)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from med_research.diseases.harvest_registry import (  # noqa: E402
    apply_harvest_reconciliation,
    drift_report,
    format_drift_errors,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report drift and exit non-zero without writing.",
    )
    args = parser.parse_args()
    if args.check:
        report = drift_report()
        errors = format_drift_errors(report)
        print(
            "harvest registry check: "
            f"discoverable={report['discoverable']} "
            f"harvest={report['harvest_entries']} "
            f"exclusions_on_disk={len(report['intentional_exclusions_on_disk'])}"
        )
        if report["intentional_exclusions_on_disk"]:
            print(
                "intentional harvest exclusions still on disk: "
                + ", ".join(report["intentional_exclusions_on_disk"])
            )
        if errors:
            print("harvest registry check failed:\n- " + "\n- ".join(errors))
            return 1
        print("harvest registry check ok")
        return 0

    report = apply_harvest_reconciliation()
    admitted = report.get("admitted") or []
    if admitted:
        print(f"admitted {len(admitted)} harvest entries: " + ", ".join(admitted))
    else:
        print("harvest registry already reconciled")
    errors = format_drift_errors(report)
    if errors:
        print("harvest registry still drifting:\n- " + "\n- ".join(errors))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
