"""Evidence Monitor API router."""

from fastapi import APIRouter

from med_research.web.models.monitor import (
    MonitorDiffResponse,
    MonitorStatusResponse,
)
from med_research.web.services.monitor_service import run_diff, run_status

router = APIRouter(tags=["Monitor"])


@router.get("/api/monitor/diff", response_model=MonitorDiffResponse)
async def monitor_diff():
    """Run a snapshot diff and return alerts.

    Takes a new snapshot and compares it against the most recent one.
    Returns changes, new publications, and severity-graded alerts.
    """
    return run_diff()


@router.get("/api/monitor/status", response_model=MonitorStatusResponse)
async def monitor_status():
    """Get current monitoring status and snapshot info."""
    return run_status()


@router.post("/api/monitor/snapshot")
def create_monitor_snapshot():
    """Manually trigger an evidence monitor snapshot."""
    from med_research.web.services.monitor_service import run_snapshot
    result = run_snapshot()
    return {"status": "snapshot_complete", "result": result}
