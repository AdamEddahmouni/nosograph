"""Parallel bulk scaffolding from local Open Targets parquet."""

from __future__ import annotations

import json
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Optional

from med_research.diseases.bulk_store import OpenTargetsBulkStore
from med_research.diseases.scaffold import (
    _diseases_root,
    _existing_disease_label,
    _load_json_list,
    build_drugs_json,
    build_genes_json,
    build_pathways_json,
    build_profile,
    build_relationships_json,
    fetch_reactome_pathways,
    generate_config_py,
    load_disease_registry,
    merge_drugs,
    merge_genes,
    merge_pathways,
    populate_scaffolded_config,
    refresh_disease,
    sanitize_id,
    scaffold_disease,
)
from med_research.logging_config import get_logger

logger = get_logger(__name__)


def collect_sources_from_bulk(
    store: OpenTargetsBulkStore,
    disease_id: str,
    name: str,
    efo_id: Optional[str] = None,
    max_genes: int = 60,
    max_drugs: int = 60,
    max_pathways: int = 30,
    use_gwas: bool = False,
    use_reactome: bool = True,
) -> dict:
    """Collect scaffold sources from the bulk store (no live OT GraphQL)."""
    resolved = store.resolve_disease(name, efo_id=efo_id)
    resolved_efo = resolved.efo_id if resolved else (efo_id or None)
    if not resolved_efo and efo_id:
        resolved_efo = efo_id
    ot_info = store.get_disease_info(resolved_efo) if resolved_efo else {}
    display_name = ot_info.get("name") or (resolved.name if resolved else name)

    ot_targets: list[dict] = []
    if resolved_efo:
        ot_targets = store.get_targets(resolved_efo, max_genes)

    gwas_genes: list[dict] = []
    if use_gwas:
        from med_research.diseases.scaffold import _gwas_genes_for_trait

        gwas_genes = _gwas_genes_for_trait(display_name, max_studies=15)

    genes_json = build_genes_json(ot_targets, gwas_genes, disease_id, max_genes)

    drugs_json: dict[str, Any] = {"drugs": []}
    if resolved_efo:
        ot_drugs = store.get_drugs(resolved_efo, max_drugs)
        drugs_json = build_drugs_json(ot_drugs)

    reactome: list[dict] = []
    if use_reactome:
        reactome = fetch_reactome_pathways(display_name, max_pathways)
    pathways_json = build_pathways_json(reactome, genes_json["genes"], max_pathways)

    return {
        "efo_id": resolved_efo,
        "name": display_name,
        "description": ot_info.get("description", ""),
        "genes": genes_json,
        "drugs": drugs_json,
        "pathways": pathways_json,
        "reactome_hits": reactome,
        "ot_targets": ot_targets,
        "gwas_genes": gwas_genes,
    }


def _harvest_one(
    disease_id: str,
    name: str,
    efo_id: Optional[str],
    bulk_root: str,
    max_genes: int,
    max_drugs: int,
    max_pathways: int,
    use_gwas: bool,
    use_reactome: bool,
    overwrite: bool,
) -> dict:
    """Worker function for parallel harvest (must be module-level for pickling)."""
    store = OpenTargetsBulkStore(bulk_root=Path(bulk_root))
    root = _diseases_root() / disease_id
    exists = root.exists() and (root / "data" / "profile.json").exists()

    if not exists:
        summary = scaffold_disease(
            disease_id=disease_id,
            name=name,
            efo_id=efo_id,
            max_genes=max_genes,
            max_drugs=max_drugs,
            max_pathways=max_pathways,
            use_gwas=use_gwas,
            use_opentargets=True,
            use_reactome=use_reactome,
            overwrite=overwrite,
            use_cache=False,
        )
        try:
            populate_scaffolded_config(disease_id)
        except Exception:
            pass
        return {"action": "scaffolded", **summary}

    sources = collect_sources_from_bulk(
        store,
        disease_id=disease_id,
        name=name,
        efo_id=efo_id,
        max_genes=max_genes,
        max_drugs=max_drugs,
        max_pathways=max_pathways,
        use_gwas=use_gwas,
        use_reactome=use_reactome,
    )
    data_dir = root / "data"
    existing_genes = _load_json_list(data_dir / "genes.json", "genes")
    existing_drugs = _load_json_list(data_dir / "drugs.json", "drugs")
    existing_pathways = _load_json_list(data_dir / "pathways.json", "pathways")

    gene_merge = merge_genes(existing_genes, sources["genes"]["genes"])
    drug_merge = merge_drugs(existing_drugs, sources["drugs"]["drugs"])
    pathway_merge = merge_pathways(existing_pathways, sources["pathways"]["pathways"])
    disease_label = _existing_disease_label(root, sources["name"], disease_id)
    relationships = build_relationships_json(
        gene_merge["genes"], drug_merge["drugs"], pathway_merge["pathways"], disease_label
    )

    for fname, payload in (
        ("genes.json", {"genes": gene_merge["genes"]}),
        ("drugs.json", {"drugs": drug_merge["drugs"]}),
        ("pathways.json", {"pathways": pathway_merge["pathways"]}),
        ("relationships.json", relationships),
    ):
        (data_dir / fname).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    try:
        populate_scaffolded_config(disease_id)
    except Exception:
        pass

    return {
        "action": "refreshed",
        "disease_id": disease_id,
        "name": sources["name"],
        "efo_id": sources["efo_id"],
        "counts": {
            "genes": len(gene_merge["genes"]),
            "drugs": len(drug_merge["drugs"]),
            "pathways": len(pathway_merge["pathways"]),
            "relationships": len(relationships["relationships"]),
        },
    }


def _gene_count(disease_id: str) -> int:
    path = _diseases_root() / disease_id / "data" / "genes.json"
    if not path.is_file():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return len(data.get("genes", []))
    except (json.JSONDecodeError, OSError):
        return 0


def bulk_harvest(
    *,
    category: Optional[str] = None,
    limit: Optional[int] = None,
    disease_ids: Optional[list[str]] = None,
    repair: bool = False,
    only_new: bool = False,
    workers: int = 8,
    max_genes: int = 60,
    max_drugs: int = 60,
    max_pathways: int = 30,
    use_gwas: bool = False,
    use_reactome: bool = True,
    overwrite: bool = False,
    registry_path: Optional[Path] = None,
) -> dict:
    """Harvest diseases in parallel from local bulk parquet."""
    store = OpenTargetsBulkStore()
    if not store.is_available():
        raise FileNotFoundError(
            "Open Targets bulk store not available. Run scripts/setup_opentargets_bulk.py first."
        )

    entries = load_disease_registry(registry_path)
    if category:
        entries = [e for e in entries if (e.get("category") or "").lower() == category.lower()]
    if disease_ids:
        wanted = {sanitize_id(d) for d in disease_ids}
        entries = [e for e in entries if sanitize_id(e.get("id", "")) in wanted]
    if repair:
        entries = sorted(
            entries,
            key=lambda e: _gene_count(sanitize_id(e.get("id", ""))),
        )
    if only_new:
        entries = [
            e
            for e in entries
            if not (_diseases_root() / sanitize_id(e.get("id", "")) / "data" / "profile.json").exists()
        ]
    if limit and limit > 0:
        entries = entries[:limit]

    bulk_root = str(store.bulk_root)
    tasks = []
    for entry in entries:
        did = sanitize_id(entry.get("id", ""))
        tasks.append(
            (
                did,
                entry.get("name") or did,
                entry.get("efo_id"),
            )
        )

    succeeded: list[dict] = []
    failed: list[dict] = []
    t0 = time.monotonic()

    if workers <= 1:
        for did, name, efo in tasks:
            try:
                result = _harvest_one(
                    did, name, efo, bulk_root, max_genes, max_drugs, max_pathways,
                    use_gwas, use_reactome, overwrite,
                )
                succeeded.append(result)
            except Exception as exc:
                failed.append({"disease_id": did, "error": str(exc)})
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(
                    _harvest_one,
                    did, name, efo, bulk_root, max_genes, max_drugs, max_pathways,
                    use_gwas, use_reactome, overwrite,
                ): did
                for did, name, efo in tasks
            }
            for future in as_completed(futures):
                did = futures[future]
                try:
                    succeeded.append(future.result())
                except Exception as exc:
                    failed.append({"disease_id": did, "error": str(exc)})

    return {
        "total": len(tasks),
        "succeeded": succeeded,
        "failed": failed,
        "elapsed_seconds": round(time.monotonic() - t0, 1),
        "workers": workers,
    }


def print_bulk_harvest_summary(report: dict) -> None:
    logger.info("\n" + "=" * 70)
    logger.info("📦 BULK HARVEST COMPLETE")
    logger.info("=" * 70)
    logger.info("  Total:     %d", report["total"])
    logger.info("  ✅ Success: %d", len(report["succeeded"]))
    logger.info("  ❌ Failed:  %d", len(report["failed"]))
    logger.info("  ⏱️  Time:    %.1fs (%d workers)", report["elapsed_seconds"], report["workers"])
    for s in report["succeeded"][:20]:
        counts = s.get("counts", {})
        logger.info(
            "    %s — %d genes, %d drugs",
            s.get("disease_id"),
            counts.get("genes", 0),
            counts.get("drugs", 0),
        )
    for f in report["failed"]:
        logger.info("    FAILED %s: %s", f["disease_id"], f["error"][:80])
    logger.info("=" * 70)
