"""Analyze diseases with empty gene lists after bulk harvest.

Writes data/reports/zero_gene_diseases.json with per-disease diagnostics.

Usage:
    python scripts/analyze_zero_gene_diseases.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from med_research.diseases.bulk_store import OpenTargetsBulkStore, normalize_disease_id
from med_research.diseases.scaffold import _diseases_root, load_disease_registry, sanitize_id

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "data" / "reports" / "zero_gene_diseases.json"


def _gene_count(disease_id: str) -> int:
    path = _diseases_root() / disease_id / "data" / "genes.json"
    if not path.is_file():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        genes = data if isinstance(data, list) else data.get("genes", [])
        return len(genes)
    except (json.JSONDecodeError, OSError):
        return 0


def main() -> int:
    store = OpenTargetsBulkStore()
    entries = []
    for entry in load_disease_registry():
        disease_id = sanitize_id(entry.get("id", ""))
        if not disease_id:
            continue
        gene_count = _gene_count(disease_id)
        if gene_count > 0:
            continue
        disease_key = entry.get("efo_id") or ""
        ot_targets = store.count_targets(disease_key) if disease_key else 0
        in_ot = bool(store.get_disease_info(disease_key)) if disease_key else False
        entries.append(
            {
                "disease_id": disease_id,
                "name": entry.get("name") or disease_id,
                "efo_id": entry.get("efo_id"),
                "mondo_id": entry.get("mondo_id"),
                "resolution_source": entry.get("resolution_source"),
                "ot_disease_row": in_ot,
                "ot_target_count": ot_targets,
                "category": entry.get("category") or "",
            }
        )

    entries.sort(key=lambda row: (row["ot_target_count"], row["disease_id"]))
    not_in_ot = [e for e in entries if not e["ot_disease_row"] and str(e.get("efo_id", "")).startswith("MONDO_")]
    in_ot_no_assoc = [e for e in entries if e["ot_disease_row"] and e["ot_target_count"] == 0]
    other = [e for e in entries if e not in not_in_ot and e not in in_ot_no_assoc]

    report = {
        "total_zero_gene": len(entries),
        "not_in_opentargets": len(not_in_ot),
        "in_opentargets_no_associations": len(in_ot_no_assoc),
        "other": len(other),
        "entries": entries,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Report: {REPORT_PATH}")
    print(
        f"Zero-gene diseases: {len(entries)} "
        f"(not in OT: {len(not_in_ot)}, in OT w/o associations: {len(in_ot_no_assoc)}, other: {len(other)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
