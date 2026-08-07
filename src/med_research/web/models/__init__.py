"""Shared and system Pydantic models."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

# ── System / Job Models ────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class JobStatus(BaseModel):
    job_id: str
    status: str  # PENDING, STARTED, SUCCESS, FAILURE
    result: Optional[Any] = None
    error: Optional[str] = None
    progress: Optional[dict[str, Any]] = None


class JobSubmitResponse(BaseModel):
    job_id: str
    status: str = "PENDING"
    module: str


class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None


# ── Platform Stats ─────────────────────────────────────────────────────────


class PlatformStats(BaseModel):
    kg_nodes: int = 0
    kg_edges: int = 0
    genes: int = 0
    drugs: int = 0
    pathways: int = 0
    candidates: int = 0
    tests_passing: int = 297


# ── Diseases Registry ─────────────────────────────────────────────────────


class DiseaseInfo(BaseModel):
    id: str
    name: str
    description: str = ""
    prevalence: str = ""
    genes: int = 0
    drugs: int = 0
    pathways: int = 0
    coverage: dict[str, Any] = Field(default_factory=dict)


class DiseasesResponse(BaseModel):
    count: int
    diseases: list[DiseaseInfo]


# ── Disease Admin (backups / prune / restore) ────────────────────────────

from med_research.web.models.disease_admin import (  # noqa: E402  (after local defs)
    BackupEntry,
    BackupsResponse,
    PruneRequest,
    PruneResponse,
    RestoreRequest,
    RestoreResponse,
)
from med_research.web.models.workspace import (  # noqa: E402  (after local defs)
    WorkspaceCompareResponse,
    WorkspaceRunListResponse,
    WorkspaceRunResponse,
    WorkspaceRunSummary,
    WorkspaceTrendPoint,
    WorkspaceTrendRun,
    WorkspaceTrendSeries,
    WorkspaceTrendsResponse,
)
