"""Evidence Monitor service — snapshot, diff, and status operations."""

from med_research.pipeline.evidence.monitor import (
    compare_snapshots,
    last_coverage,
    list_snapshots,
    load_latest_snapshots,
    take_snapshot,
)


def run_snapshot(
    sources: list = None,
    max_per_query: int = 10,
    disease_id: str = "sle",
) -> dict:
    """Take a new evidence snapshot and return snapshot info."""
    return take_snapshot(
        sources=sources,
        max_per_query=max_per_query,
        disease_id=disease_id,
    )


def run_diff(disease_id: str = "sle") -> dict:
    """Run a snapshot diff and return results."""
    snapshots = load_latest_snapshots(2)

    if len(snapshots) < 2:
        # Need a baseline
        prev = take_snapshot(disease_id=disease_id)
        curr = take_snapshot(disease_id=disease_id)
        snapshots = [prev, curr]

    prev, curr = snapshots
    diff = compare_snapshots(prev, curr)
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
