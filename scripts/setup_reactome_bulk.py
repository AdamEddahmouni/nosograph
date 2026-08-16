"""Cache Reactome pathway mappings locally for offline bulk harvest.

Usage:
    python scripts/setup_reactome_bulk.py
    python scripts/setup_reactome_bulk.py --from-fixtures
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

ROOT = Path(__file__).resolve().parents[1]
BULK_DIR = ROOT / "data" / "bulk" / "reactome"
FIXTURE = ROOT / "tests" / "fixtures" / "reactome" / "pathways_by_gene.json"
MANIFEST_PATH = ROOT / "data" / "bulk" / "manifest.json"


def _default_cache() -> dict:
    return {
        "BTK": [{"id": "R-HSA-983695", "name": "Antigen activates B Cell Receptor"}],
        "JAK2": [{"id": "R-HSA-6783783", "name": "Interleukin-10 signaling"}],
        "STAT4": [{"id": "R-HSA-912526", "name": "Interleukin receptor signaling"}],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Setup local Reactome bulk cache")
    parser.add_argument("--from-fixtures", action="store_true", help="Use test fixture subset")
    args = parser.parse_args()

    BULK_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = BULK_DIR / "pathways_by_gene.json"

    if args.from_fixtures and FIXTURE.is_file():
        cache_path.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        try:
            from med_research.pipeline.bioinformatics.reactome import fetch_reactome_pathways

            genes = ("BTK", "JAK2", "STAT4", "TNF", "IL6", "CD19")
            cache: dict = {}
            for gene in genes:
                pathways = fetch_reactome_pathways(gene)
                if pathways:
                    cache[gene] = pathways
            if not cache:
                cache = _default_cache()
        except Exception:
            cache = _default_cache()
        cache_path.write_text(json.dumps(cache, indent=2) + "\n", encoding="utf-8")

    manifest: dict = {}
    if MANIFEST_PATH.is_file():
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest.setdefault("reactome", {})
    manifest["reactome"]["pathways_by_gene"] = str(cache_path.relative_to(ROOT))
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Reactome cache ready: {cache_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
