"""Refresh disease modules in batches from the curated registry.

Use this after `batch-add` to populate genes/drugs/pathways from public APIs.
GWAS is slow (~30s/disease); skip it for fast passes and refresh with GWAS later.

Examples:
    python scripts/batch_refresh_diseases.py --limit 100
    python scripts/batch_refresh_diseases.py --limit 100 --offset 100 --skip-gwas
    python scripts/batch_refresh_diseases.py --empty-only --limit 50
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Allow running from repo root without install
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from med_research.diseases.scaffold import load_disease_registry, print_refresh_summary, refresh_disease


def _has_genes(disease_id: str, root: Path) -> bool:
    genes_path = root / disease_id / "data" / "genes.json"
    if not genes_path.is_file():
        return False
    try:
        data = json.loads(genes_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return bool(data.get("genes"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh disease modules in batches")
    parser.add_argument("--limit", type=int, default=100, help="Max diseases to refresh (default: 100)")
    parser.add_argument("--offset", type=int, default=0, help="Skip first N candidates (default: 0)")
    parser.add_argument("--empty-only", action="store_true", help="Only refresh modules with no genes")
    parser.add_argument("--skip-gwas", action="store_true", help="Skip GWAS Catalog (much faster)")
    parser.add_argument("--skip-opentargets", action="store_true", help="Skip Open Targets")
    parser.add_argument("--skip-reactome", action="store_true", help="Skip Reactome")
    parser.add_argument("--delay", type=float, default=0.5, help="Seconds between refreshes")
    args = parser.parse_args()

    from med_research.diseases import scaffold as scaffold_mod

    diseases_root = Path(scaffold_mod.__file__).parent
    registry = load_disease_registry()

    candidates = [d["id"] for d in registry]
    if args.empty_only:
        candidates = [did for did in candidates if not _has_genes(did, diseases_root)]

    batch = candidates[args.offset : args.offset + args.limit]
    if not batch:
        print(f"No diseases to refresh (offset={args.offset}, limit={args.limit}).")
        return 0

    print(f"Refreshing {len(batch)} diseases (offset={args.offset}, empty_only={args.empty_only})")
    t0 = time.monotonic()
    ok, failed = 0, []

    for idx, disease_id in enumerate(batch, 1):
        print(f"[{idx}/{len(batch)}] {disease_id}...", flush=True)
        try:
            summary = refresh_disease(
                disease_id,
                use_gwas=not args.skip_gwas,
                use_opentargets=not args.skip_opentargets,
                use_reactome=not args.skip_reactome,
            )
            print_refresh_summary(summary)
            ok += 1
        except Exception as exc:
            print(f"  FAILED {disease_id}: {type(exc).__name__}: {exc}")
            failed.append(disease_id)
        if idx < len(batch) and args.delay > 0:
            time.sleep(args.delay)

    elapsed = time.monotonic() - t0
    print(f"\nDone: {ok} refreshed, {len(failed)} failed, {elapsed:.0f}s")
    if failed:
        print("Failed:", ", ".join(failed[:20]))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
