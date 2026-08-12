"""Audit log for disease module mutations (prune / restore).

Every prune and restore that writes files is recorded as one JSON line in
``data/audit_log.jsonl`` inside the disease module, capturing the timestamp,
the disease, exactly which entities were removed/restored, and the backup
file involved — so module changes are traceable whether they came from the
CLI or the web dashboard.

The log is append-only JSONL: lines are small and self-contained, so a crash
mid-write at worst truncates the trailing line (skipped on read with a
warning), and concurrent appends never clobber each other. Recording is
best-effort — a failed audit write never fails the prune/restore itself.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from med_research.diseases.scaffold import sanitize_id
from med_research.logging_config import get_logger

logger = get_logger(__name__)

AUDIT_LOG_NAME = "audit_log.jsonl"
AUDIT_VERSION = 1


def _diseases_root() -> Path:
    import med_research.diseases as diseases_pkg

    return Path(diseases_pkg.__file__).parent


def audit_path(disease_id: str, target_dir: Optional[Path] = None) -> Path:
    """Resolve the audit log path for a disease module.

        ``disease_id`` is sanitized like ``scaffold.list_backups`` — an id from
    the web URL can carry path separators, and we must never resolve outside
    the diseases dir. ``target_dir`` is the module root (containing ``data/``)
    — used by tests.
    """
    disease_id = sanitize_id(disease_id or "")
    root = target_dir or (_diseases_root() / disease_id)
    return root / "data" / AUDIT_LOG_NAME


def append_audit(
    disease_id: str,
    entry: dict,
    target_dir: Optional[Path] = None,
) -> Optional[Path]:
    """Append one audit entry as a JSON line.

    ``ts`` (ISO-8601 local time, second precision) and ``version`` are added
    automatically. Returns the log path, or ``None`` if the write failed —
    the caller's mutation still succeeded; auditing must never block it.
    """
    row = {
        "version": AUDIT_VERSION,
        "ts": datetime.now().isoformat(timespec="seconds"),
        **entry,
    }
    path = audit_path(disease_id, target_dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return path
    except OSError as e:  # noqa: BLE001 — audit failure must not break the mutation
        logger.warning("Could not append audit entry for '%s': %s", disease_id, e)
        return None


def read_audit(
    disease_id: str,
    limit: Optional[int] = None,
    target_dir: Optional[Path] = None,
) -> list[dict]:
    """Return audit entries in chronological order (append order).

    Corrupt or truncated lines are skipped with a warning. Raises
    FileNotFoundError for a module that doesn't exist (mirrors
    ``scaffold.list_backups``); an existing module with no audit log yet
    returns ``[]``.
    """
    disease_id = sanitize_id(disease_id or "")
    root = target_dir or (_diseases_root() / disease_id)
    if not (root / "__init__.py").exists():
        raise FileNotFoundError(
            f"No disease module '{disease_id}' found at {root}. "
            "Run 'med-research disease add <id>' first."
        )
    path = audit_path(disease_id, target_dir)
    if not path.exists():
        return []
    entries: list[dict] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            logger.warning("Skipping corrupt audit line %d in %s", line_no, path)
    if limit is not None and limit > 0:
        return entries[-limit:]
    return entries


def prune_entry(summary: dict) -> dict:
    """Build the audit entry for a refresh+prune that wrote files."""
    prune_info = summary.get("prune", {})
    return {
        "action": "prune",
        "disease_id": summary.get("disease_id", ""),
        "name": summary.get("name", ""),
        "removed": {
            "genes": prune_info.get("genes", []),
            "drugs": prune_info.get("drugs", []),
        },
        "scrubbed_pathways": prune_info.get("scrubbed_pathways", []),
        "backup": prune_info.get("backup"),
        "merge": {
            kind: {k: len(v) for k, v in (summary.get("merge", {}).get(kind) or {}).items()}
            for kind in ("genes", "drugs", "pathways")
        },
        "counts": summary.get("counts", {}),
    }


def restore_entry(summary: dict) -> dict:
    """Build the audit entry for a restore that wrote files."""
    return {
        "action": "restore",
        "disease_id": summary.get("disease_id", ""),
        "name": "",
        "backup": summary.get("backup", ""),
        "backup_disease_id": summary.get("backup_disease_id"),
        "restored": summary.get("restored", {}),
        "skipped": summary.get("skipped", {}),
        "updated_pathways": summary.get("updated_pathways", []),
        "counts": summary.get("counts", {}),
    }
