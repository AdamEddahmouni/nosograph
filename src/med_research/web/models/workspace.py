"""Pydantic response models for saved workspace runs."""

from typing import Any

from pydantic import BaseModel, Field


class WorkspaceRunSummary(BaseModel):
    run_id: str
    disease_id: str
    question: str
    status: str
    error: str | None = None
    evidence_count: int = 0
    claim_count: int = 0
    drug_count: int = 0
    target_count: int = 0
    created_at: str
    updated_at: str


class WorkspaceRunListResponse(BaseModel):
    runs: list[WorkspaceRunSummary] = Field(default_factory=list)
    limit: int
    offset: int


class WorkspaceRunResponse(BaseModel):
    run_id: str
    status: str
    request: dict[str, Any]
    dossier: dict[str, Any] | None = None
    html: str | None = None
    error: str | None = None
    created_at: str
    updated_at: str


class WorkspaceTrendPoint(BaseModel):
    run_id: str
    timestamp: str
    score: float | None = None
    rank: int | None = None
    confidence_band: str | None = None
    supporting_claim_count: int = 0
    contradicting_claim_count: int = 0
    present: bool = False


class WorkspaceTrendSeries(BaseModel):
    candidate_id: str
    name: str
    points: list[WorkspaceTrendPoint] = Field(default_factory=list)


class WorkspaceTrendRun(BaseModel):
    run_id: str
    question: str
    timestamp: str
    evidence_count: int = 0
    claim_count: int = 0
    warning_count: int = 0
    source_coverage: dict[str, dict[str, Any]] = Field(default_factory=dict)


class WorkspaceTrendsResponse(BaseModel):
    runs: list[WorkspaceTrendRun] = Field(default_factory=list)
    drug_series: list[WorkspaceTrendSeries] = Field(default_factory=list)
    target_series: list[WorkspaceTrendSeries] = Field(default_factory=list)


class WorkspaceCompareResponse(BaseModel):
    left_run_id: str
    right_run_id: str
    left: dict[str, Any]
    right: dict[str, Any]
    drug_changes: list[dict[str, Any]] = Field(default_factory=list)
    target_changes: list[dict[str, Any]] = Field(default_factory=list)
    evidence_changes: dict[str, list[str]] = Field(default_factory=dict)
    summary: dict[str, int] = Field(default_factory=dict)
