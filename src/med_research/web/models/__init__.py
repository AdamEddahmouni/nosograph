"""Shared and system Pydantic models."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

try:
    from importlib.metadata import version as package_version
except ImportError:  # pragma: no cover
    from importlib_metadata import version as package_version  # type: ignore[no-redef]

# ── System / Job Models ────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = Field(default_factory=lambda: package_version("med-research"))
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


class PipelineModuleCatalogEntry(BaseModel):
    """OpenAPI shape for registry-generated module metadata."""

    module_id: str
    aliases: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    coverage_inputs: list[str] = Field(default_factory=list)
    coverage_module: str
    result_contract: str | None = None
    response_schema: dict[str, Any] = Field(default_factory=dict)
    request_schema: dict[str, Any] = Field(default_factory=dict)
    request_validators: list[dict[str, Any]] = Field(default_factory=list)
    cli_command: str
    cli_help: str
    celery_task: str
    job_aliases: list[str] = Field(default_factory=list)
    persisted_request_schema_version: str | None = Field(
        default=None,
        description="Version of the persisted request schema, when this module has run storage.",
    )
    persisted_result_schema_version: str | None = Field(
        default=None,
        description="Version of the persisted result schema, when this module has run storage.",
    )
    persisted_request_schema: dict[str, Any] | None = Field(
        default=None,
        description="JSON Schema for the persisted request payload.",
    )
    persisted_result_schema: dict[str, Any] | None = Field(
        default=None,
        description="JSON Schema for the persisted result payload.",
    )
    coverage: dict[str, Any] = Field(default_factory=dict)


class PipelineModulesResponse(BaseModel):
    count: int
    disease_id: str
    modules: list[PipelineModuleCatalogEntry] = Field(default_factory=list)


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
    WorkspaceAlert,
    WorkspaceAlertListResponse,
    WorkspaceCandidateHistoryPoint,
    WorkspaceCandidateHistoryResponse,
    WorkspaceCandidateReview,
    WorkspaceCandidateReviewRequest,
    WorkspaceCompareResponse,
    WorkspaceDigestDecision,
    WorkspaceDigestEvidence,
    WorkspaceEvidenceGraphResponse,
    WorkspaceGraphEdge,
    WorkspaceGraphNode,
    WorkspaceNotificationDelivery,
    WorkspaceNotificationSettings,
    WorkspaceNotificationSettingsRequest,
    WorkspaceReviewListResponse,
    WorkspaceRunListResponse,
    WorkspaceRunResponse,
    WorkspaceRunSummary,
    WorkspaceTrendPoint,
    WorkspaceTrendRun,
    WorkspaceTrendSeries,
    WorkspaceTrendsResponse,
    WorkspaceWeeklyDigestResponse,
)
