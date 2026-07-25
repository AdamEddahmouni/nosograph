"""Evidence Monitor service — snapshot, diff, and status operations."""

from med_research.pipeline.evidence.monitor import (
    compare_snapshots,
    list_snapshots,
    load_latest_snapshots,
    take_snapshot,
)


def run_snapshot(sources: list = None, max_per_query: int = 10) -> dict:
    """Take a new evidence snapshot and return snapshot info."""
    return take_snapshot(sources=sources, max_per_query=max_per_query)


def run_diff() -> dict:
    """Run a snapshot diff and return results."""
    snapshots = load_latest_snapshots(2)

    if len(snapshots) < 2:
        # Need a baseline
        prev = take_snapshot()
        curr = take_snapshot()
        snapshots = [prev, curr]

    prev, curr = snapshots
    return compare_snapshots(prev, curr)


def run_status() -> dict:
    """Get the current monitoring status."""
    snapshots = list_snapshots()
    return {
        "snapshots_available": len(snapshots),
        "last_snapshot": snapshots[0].stem if snapshots else None,
    }
