"""Disease admin service — module lifecycle behind the web API.

Wraps the scaffold engine's ``refresh_disease`` / ``restore_disease`` /
``list_backups`` so the dashboard can prune and restore a module exactly as
the CLI does. After any *write* the knowledge-graph caches for the disease
are invalidated so the next request rebuilds from the updated data files.
"""

from pathlib import Path
from typing import Any, Optional

# Note: the scaffold module is imported inside each function so tests can
# monkeypatch it at the module level (matches the CLI's lazy-import pattern).


def _invalidate_disease_caches() -> None:
    """Drop the in-memory KG/entity caches after a data-file mutation."""
    from med_research.web.dependencies import (
        get_kg_drugs,
        get_kg_genes,
        get_kg_pathways,
        get_knowledge_graph,
    )

    for loader in (get_knowledge_graph, get_kg_genes, get_kg_drugs, get_kg_pathways):
        loader.cache_clear()


def list_disease_backups(disease_id: str) -> dict:
    """Inventory the pruned backups for a disease (newest first)."""
    from med_research.diseases.scaffold import list_backups

    return list_backups(disease_id)


def _prune_options(req: Any) -> dict:
    return {
        "max_genes": req.max_genes,
        "max_drugs": req.max_drugs,
        "max_pathways": req.max_pathways,
        "use_gwas": not req.skip_gwas,
        "use_opentargets": not req.skip_opentargets,
        "use_reactome": not req.skip_reactome,
        "use_cache": not req.no_cache,
    }


def preview_prune(disease_id: str, req: Any) -> dict:
    """Dry-run refresh+prune: returns merge + prune candidates, writes nothing."""
    from med_research.diseases.scaffold import refresh_disease

    summary = refresh_disease(
        disease_id, prune=True, dry_run=True, confirm=None, **_prune_options(req)
    )
    return _prune_payload(disease_id, summary)


def apply_prune(disease_id: str, req: Any) -> dict:
    """Real refresh+prune: writes files, backs up pruned entities."""
    from med_research.diseases.scaffold import refresh_disease

    summary = refresh_disease(
        disease_id, prune=True, dry_run=False, confirm=lambda plan: True, **_prune_options(req)
    )
    # Safety net: if every source returned nothing (network down / all sources
    # skipped), *every* existing entity would be flagged as "not reported" and
    # the whole module dropped. Refuse rather than prune blindly.
    if not any(summary.get("sources", {}).values()):
        raise ValueError(
            "All sources returned nothing (GWAS/Open Targets/Reactome) — refusing to "
            "prune because every entity would be flagged as 'not reported'. Check "
            "network access or skip fewer sources, then retry."
        )
    _invalidate_disease_caches()
    return _prune_payload(disease_id, summary)


def _prune_payload(disease_id: str, summary: dict) -> dict:
    return {
        "disease_id": disease_id,
        "preview": summary.get("dry_run", False),
        "name": summary.get("name", ""),
        "efo_id": summary.get("efo_id"),
        "sources": summary.get("sources", {}),
        "merge": summary.get("merge", {}),
        "prune": summary.get("prune", {}),
        "counts": summary.get("counts", {}),
        "files": summary.get("files", []),
    }


def _resolve_backup_path(disease_id: str, backup: str | None) -> str | None:
    """Accept a full path or a bare filename inside the module's backups dir.

    ``None`` → the newest backup (resolved by restore_disease); an empty or
    whitespace-only string is rejected rather than silently meaning "newest".
    """
    if backup is None:
        return None  # restore_disease resolves the newest backup
    if not backup.strip():
        raise ValueError("'backup' must be a path or filename, or omitted to use the newest backup")
    path = Path(backup)
    if path.exists():
        return str(path)
    # Bare filename → look it up in the module's inventory
    from med_research.diseases.scaffold import list_backups

    inventory = list_backups(disease_id)
    for entry in inventory.get("backups", []):
        if Path(entry["path"]).name == backup:
            return str(entry["path"])
    return str(path)  # let restore_disease raise the precise error


def preview_restore(disease_id: str, backup: Optional[str]) -> dict:
    from med_research.diseases.scaffold import restore_disease

    summary = restore_disease(
        disease_id, backup_path=_resolve_backup_path(disease_id, backup), dry_run=True
    )
    return _restore_payload(disease_id, summary)


def apply_restore(disease_id: str, backup: Optional[str]) -> dict:
    from med_research.diseases.scaffold import restore_disease

    summary = restore_disease(
        disease_id, backup_path=_resolve_backup_path(disease_id, backup), dry_run=False
    )
    _invalidate_disease_caches()
    return _restore_payload(disease_id, summary)


def _restore_payload(disease_id: str, summary: dict) -> dict:
    return {
        "disease_id": disease_id,
        "backup": summary.get("backup", ""),
        "backup_disease_id": summary.get("backup_disease_id"),
        "preview": summary.get("dry_run", False),
        "restored": summary.get("restored", {}),
        "skipped": summary.get("skipped", {}),
        "updated_pathways": summary.get("updated_pathways", []),
        "counts": summary.get("counts", {}),
        "files": summary.get("files", []),
    }


def list_disease_audit(disease_id: str, limit: int = 20) -> dict:
    """Read a module's audit log, newest first (last ``limit`` entries).

    Entries are appended by the scaffold engine itself (``refresh_disease`` /
    ``restore_disease``), so CLI and dashboard mutations are both recorded.
    Returns ``{"disease_id", "count", "entries"}`` where ``count`` is the
    total number of logged actions.
    """
    from med_research.diseases import audit
    from med_research.diseases.scaffold import sanitize_id

    # Sanitize like list_backups: the path param can carry separators and must
    # never resolve outside the diseases dir. The response echoes the clean id.
    disease_id = sanitize_id(disease_id or "")
    limit = max(1, min(int(limit), 500))
    entries = audit.read_audit(disease_id)  # chronological; raises for missing module
    return {
        "disease_id": disease_id,
        "count": len(entries),
        "entries": list(reversed(entries[-limit:])),
    }
