"""Remove non-disease entries from disease_registry.json.

Usage:
    python scripts/purge_registry_non_diseases.py --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from med_research.diseases.registry_quality import filter_disease_entries
from med_research.diseases.scaffold import load_disease_registry, save_disease_registry


def main() -> int:
    parser = argparse.ArgumentParser(description="Purge non-disease registry entries")
    parser.add_argument("--apply", action="store_true", help="Write filtered registry")
    args = parser.parse_args()

    registry = load_disease_registry()
    kept, rejected = filter_disease_entries(registry)
    print(f"Registry: {len(registry)} entries, would remove {len(rejected)}")
    for rid in rejected:
        print(f"  - {rid}")

    if args.apply and rejected:
        save_disease_registry(kept)
        print(f"Saved {len(kept)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
