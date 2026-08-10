"""Evidence Monitor service — snapshot, diff, and status via registry."""

from typing import Any, cast

from med_research.pipeline.evidence.monitor import last_coverage, list_snapshots
from med_research.web.services.registry_service import dispatch_sync_module


def run_snapshot(
    sources: list | None = None,
    max_per_query: int = 10,
    disease_id: str = "sle",
) -> dict:
    """Take a new evidence snapshot via the evidence_monitor registry adapter."""
    result = dispatch_sync_module(
        "evidence_monitor",
        disease_id,
        sources=sources,
        max_per_query=max_per_query,
    )
    return cast(dict[str, Any], result.get("snapshot", result))


def run_diff(disease_id: str = "sle") -> dict:
    """Run a snapshot diff via the evidence_monitor registry adapter."""
    result = dispatch_sync_module("evidence_monitor", disease_id, diff=True)
    diff = cast(dict[str, Any], result.get("diff", result))
    if last_coverage:
        diff["coverage"] = last_coverage.to_dict()
    return diff


def run_status() -> dict:
    """Get the current monitoring status."""
    snapshots = list_snapshots()
    return {
        "snapshots_available": len(snapshots),
        "last_snapshot": snapshots[0].stem if snapshots else None,
    }
