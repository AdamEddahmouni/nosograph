"""Pydantic models for the Evidence Monitor API."""

from typing import Optional

from pydantic import BaseModel, Field


class AlertItem(BaseModel):
    """A single alert from the evidence monitor."""

    type: str = ""
    entity: str = ""
    entity_type: str = ""
    new_count: int = 0
    new_items: list[dict] = Field(default_factory=list)
    severity: str = "low"


class ChangeSummary(BaseModel):
    """Summary of changes between two snapshots."""

    new_queries: list[str] = Field(default_factory=list)
    changed_queries: list[str] = Field(default_factory=list)
    new_drugs: list[str] = Field(default_factory=list)
    changed_drugs: list[str] = Field(default_factory=list)
    new_genes: list[str] = Field(default_factory=list)
    changed_genes: list[str] = Field(default_factory=list)


class MonitorDiffResponse(BaseModel):
    """Full evidence monitor diff response."""

    prev_snapshot: str = ""
    curr_snapshot: str = ""
    prev_timestamp: str = ""
    curr_timestamp: str = ""
    hours_elapsed: float = 0.0
    total_changes: int = 0
    alerts: list[AlertItem] = Field(default_factory=list)
    changes: ChangeSummary = Field(default_factory=ChangeSummary)
    generated_at: str = ""


class SnapshotInfo(BaseModel):
    """Information about a single snapshot."""

    snapshot_id: str
    timestamp: str
    query_count: int = 0
    drug_count: int = 0
    gene_count: int = 0


class SnapshotListResponse(BaseModel):
    """List of available snapshots."""

    snapshots: list[SnapshotInfo] = Field(default_factory=list)
    total: int = 0


class MonitorStatusResponse(BaseModel):
    """Current monitoring status."""

    snapshots_available: int = 0
    last_snapshot: Optional[str] = None
    last_diff: Optional[str] = None
    tracked_queries: int = 0
    tracked_drugs: int = 0
    tracked_genes: int = 0
