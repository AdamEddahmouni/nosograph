"""Disease Admin API models — module lifecycle (backups / prune / restore).

These mirror the CLI's `med-research disease` commands so the dashboard can
evolve a module (re-merge sources, drop stale entities, roll back prunes)
without touching the terminal.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field

# ── Backups ───────────────────────────────────────────────────────────────


class BackupEntry(BaseModel):
    """One pruned-backup file with what restoring it would bring back."""

    path: str
    size_bytes: int = 0
    modified: str = ""
    genes: list[str] = []
    drugs: list[str] = []
    readable: bool = True


class BackupsResponse(BaseModel):
    disease_id: str
    count: int
    total_size_bytes: int = 0
    backups: list[BackupEntry] = []


# ── Prune (refresh + drop entities no source reports) ────────────────────


class PruneRequest(BaseModel):
    """Two-phase prune: preview by default, `apply: true` writes.

    The preview (dry-run) returns the merge + prune candidates without
    touching disk; `apply: true` performs the real refresh+prune, backing up
    removed entities — the API analogue of the CLI's confirmation prompt.
    """

    apply: bool = False
    max_genes: int = Field(60, ge=1, le=200, description="Max genes to fetch from sources")
    max_drugs: int = Field(60, ge=0, le=200, description="Max drugs to fetch from sources")
    max_pathways: int = Field(30, ge=0, le=100, description="Max pathways to fetch")
    skip_gwas: bool = False
    skip_opentargets: bool = False
    skip_reactome: bool = False
    no_cache: bool = False


class PruneResponse(BaseModel):
    disease_id: str
    preview: bool  # True when this was a dry-run (nothing written)
    name: str = ""
    efo_id: Optional[str] = None
    sources: dict[str, bool] = {}
    merge: dict[str, Any] = {}
    prune: dict[str, Any] = {}
    counts: dict[str, int] = {}
    files: list[str] = []


# ── Restore (re-merge a pruned backup) ───────────────────────────────────


class RestoreRequest(BaseModel):
    """Restore a backup. `backup` is a full path or a bare filename inside
    the module's data/backups/ dir; omitted → the newest backup."""

    backup: Optional[str] = None
    apply: bool = False  # False = preview (dry-run)


class RestoreResponse(BaseModel):
    disease_id: str
    backup: str
    backup_disease_id: Optional[str] = None
    preview: bool
    restored: dict[str, list[str]] = {}
    skipped: dict[str, list[str]] = {}
    updated_pathways: list[str] = []
    counts: dict[str, int] = {}
    files: list[str] = []


# ── Audit log (traceable prune / restore history) ───────────────────────


class AuditEntry(BaseModel):
    """One recorded prune/restore mutation.

    Written server-side to the module's ``data/audit_log.jsonl`` by the
    scaffold engine whenever a prune or restore writes files.
    """

    version: int = 1
    ts: str
    action: str  # "prune" | "restore"
    disease_id: str
    name: str = ""
    backup: Optional[str] = None
    backup_disease_id: Optional[str] = None
    removed: dict[str, list[str]] = {}
    restored: dict[str, list[str]] = {}
    skipped: dict[str, list[str]] = {}
    scrubbed_pathways: list[str] = []
    updated_pathways: list[str] = []
    merge: dict[str, Any] = {}
    counts: dict[str, int] = {}


class AuditResponse(BaseModel):
    disease_id: str
    count: int  # total entries in the log
    entries: list[AuditEntry] = []  # newest-first, up to the requested limit
