#!/usr/bin/env python3
"""CLI utility for disease module validation and curation auditing."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure package is on path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from med_research.diseases.base import Disease, list_available_diseases
from med_research.diseases.coverage import module_coverage
from med_research.logging_config import setup_logging, get_logger

logger = get_logger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit and curate disease module coverage.")
    parser.add_argument("disease_id", nargs="?", help="Disease ID to inspect (e.g., sle, ra, ibd)")
    parser.add_argument("--all", action="store_true", help="Audit all 500+ registered disease modules")
    args = parser.parse_args()

    setup_logging()

    if args.all:
        diseases = list_available_diseases()
        logger.info("Auditing coverage for %d diseases...", len(diseases))
        curated_cnt = 0
        for d_id in diseases:
            cov = module_coverage(d_id)
            if cov.tier == "full":
                curated_cnt += 1
        logger.info("Summary: %d / %d diseases fully curated.", curated_cnt, len(diseases))
        return 0

    if not args.disease_id:
        parser.print_help()
        return 1

    d_id = args.disease_id.lower()
    try:
        disease = Disease(d_id)
        profile = disease.load_profile()
        cov = module_coverage(d_id)
        print(f"\n--- Disease Curation Audit: {d_id.upper()} ---")
        print(f"Name: {profile.get('name', 'N/A')}")
        print(f"Coverage Tier: {cov.tier}")
        print(f"Supported Modules ({len(cov.supported_modules)}): {', '.join(cov.supported_modules)}")
        print(f"Unsupported Modules ({len(cov.unsupported_modules)}): {', '.join(cov.unsupported_modules)}")
        print(f"Coverage Fingerprint: {cov.fingerprint}\n")
    except Exception as exc:
        logger.error("Failed to load disease '%s': %s", d_id, exc)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
