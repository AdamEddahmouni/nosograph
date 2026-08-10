"""Pydantic response models for saved workspace runs."""

from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator

from med_research.pipeline.evidence_workspace.schemas import (
    WorkspaceRequestV1,
    WorkspaceResultV1,
)

CandidateType = Literal["drug", "target"]

CandidateDecision = Literal["unreviewed", "pinned", "rejected"]
GraphNodeType = Literal[
    "candidate",
    "claim",
    "citation",
    "pathway",
    "decision",
    "disease",
    "knowledge_graph",
]


class WorkspaceGraphNode(BaseModel):
    id: str
    type: GraphNodeType
    label: str
    subtitle: str = ""
    description: str = ""
    url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkspaceGraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str
    label: str = ""


class WorkspaceEvidenceGraphResponse(BaseModel):
    run_id: str
    researcher_id: str = "anonymous"
    nodes: list[WorkspaceGraphNode] = Field(default_factory=list)
    edges: list[WorkspaceGraphEdge] = Field(default_factory=list)


class WorkspaceAlert(BaseModel):
    alert_id: str
    researcher_id: str = "anonymous"
    kind: Literal["review_reminder"] = "review_reminder"
    candidate_id: str
    candidate_type: CandidateType
    candidate_name: str
    reviewed_run_id: str
    trigger_run_id: str
    title: str
    message: str
    evidence_added: list[str] = Field(default_factory=list)
    evidence_removed: list[str] = Field(default_factory=list)
    previous_score: float | None = None
    current_score: float | None = None
    score_drop: float = 0.0
    previous_rank: int | None = None
    current_rank: int | None = None
    rank_change: int = 0
    previous_quality: float | None = None
    current_quality: float | None = None
    quality_change: float | None = None
    trigger_reasons: list[str] = Field(default_factory=list)
    created_at: str
    read_at: str | None = None


class WorkspaceAlertListResponse(BaseModel):
    alerts: list[WorkspaceAlert] = Field(default_factory=list)
    unread_count: int = 0
    limit: int
    offset: int


class WorkspaceNotificationSettingsRequest(BaseModel):
    email: str = Field(default="", max_length=320)
    email_enabled: bool = True
    slack_webhook_url: str = Field(default="", max_length=500)
    slack_enabled: bool = True
    score_drop_threshold: float = Field(default=0.0, ge=0.0, le=100.0)
    rank_change_threshold: int = Field(default=0, ge=0, le=100)
    evidence_quality_change_threshold: float = Field(default=0.0, ge=0.0, le=1.0)
    weekly_digest_enabled: bool = False
    weekly_digest_weekday: int = Field(default=0, ge=0, le=6)
    weekly_digest_hour: int = Field(default=9, ge=0, le=23)
    weekly_digest_minute: int = Field(default=0, ge=0, le=59)
    weekly_digest_timezone: str = Field(default="UTC", min_length=1, max_length=64)

    @field_validator("weekly_digest_timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        normalized = value.strip()
        try:
            ZoneInfo(normalized)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("weekly_digest_timezone must be a valid IANA timezone") from exc
        return normalized

    @field_validator("email", "slack_webhook_url", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str) -> str:
        return str(value or "").strip()

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if value and ("@" not in value or value.startswith("@") or value.endswith("@")):
            raise ValueError("email must be a valid email address")
        return value


class WorkspaceNotificationDelivery(BaseModel):
    status: Literal["delivered", "failed"] | None = None
    attempts: int = 0
    last_attempt_at: str | None = None
    delivered_at: str | None = None
    error: str | None = None


class WorkspaceNotificationSettings(BaseModel):
    researcher_id: str
    email: str = ""
    email_enabled: bool = True
    slack_configured: bool = False
    slack_enabled: bool = True
    score_drop_threshold: float = 0.0
    rank_change_threshold: int = 0
    evidence_quality_change_threshold: float = 0.0
    weekly_digest_enabled: bool = False
    weekly_digest_weekday: int = 0
    weekly_digest_hour: int = 9
    weekly_digest_minute: int = 0
    weekly_digest_timezone: str = "UTC"
    delivery: dict[str, WorkspaceNotificationDelivery] = Field(default_factory=dict)
    digest_delivery: dict[str, WorkspaceNotificationDelivery] = Field(default_factory=dict)
    updated_at: str | None = None


class WorkspaceDigestEvidence(BaseModel):
    evidence_id: str
    candidate_id: str
    candidate_type: CandidateType
    candidate_name: str
    trigger_run_id: str
    created_at: str


class WorkspaceDigestDecision(BaseModel):
    event_id: int
    run_id: str
    candidate_id: str
    candidate_type: CandidateType
    previous_decision: str
    decision: str
    rationale: str = ""
    notes: str = ""
    changed_my_mind: str = ""
    recorded_at: str


class WorkspaceWeeklyDigestResponse(BaseModel):
    researcher_id: str
    digest_key: str
    period_start: str
    period_end: str
    generated_at: str
    new_evidence: list[WorkspaceDigestEvidence] = Field(default_factory=list)
    unresolved_reminders: list[WorkspaceAlert] = Field(default_factory=list)
    changed_decisions: list[WorkspaceDigestDecision] = Field(default_factory=list)
    new_evidence_count: int = 0
    unresolved_reminder_count: int = 0
    changed_decision_count: int = 0
    markdown: str = ""
    review_url: str | None = None


class WorkspaceCandidateReviewRequest(BaseModel):
    candidate_id: str = Field(min_length=1, max_length=200)
    candidate_type: CandidateType
    decision: CandidateDecision = "unreviewed"
    rationale: str = Field(default="", max_length=2000)
    notes: str = Field(default="", max_length=5000)
    tags: list[str] = Field(default_factory=list, max_length=20)
    changed_my_mind: str = Field(default="", max_length=3000)


class WorkspaceCandidateReview(WorkspaceCandidateReviewRequest):
    run_id: str
    researcher_id: str = "anonymous"
    candidate_name: str = ""
    provenance_fingerprint: str = ""
    created_at: str
    updated_at: str


class WorkspaceReviewListResponse(BaseModel):
    run_id: str
    reviews: list[WorkspaceCandidateReview] = Field(default_factory=list)


class WorkspaceCandidateHistoryPoint(BaseModel):
    run_id: str
    timestamp: str
    score: float | None = None
    rank: int | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    evidence_added: list[str] = Field(default_factory=list)
    evidence_removed: list[str] = Field(default_factory=list)
    review: WorkspaceCandidateReview | None = None


class WorkspaceCandidateHistoryResponse(BaseModel):
    candidate_id: str
    candidate_type: CandidateType
    candidate_name: str = ""
    points: list[WorkspaceCandidateHistoryPoint] = Field(default_factory=list)


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
    request_schema_version: Literal["1.0"] = Field(
        default="1.0",
        description="Persisted Workspace request schema version.",
    )
    result_schema_version: Literal["1.1"] = Field(
        default="1.1",
        description="Persisted Workspace result schema version.",
    )
    request: WorkspaceRequestV1 = Field(
        description="Versioned persisted Workspace request payload."
    )
    dossier: WorkspaceResultV1 | None = Field(
        default=None,
        description="Versioned persisted Workspace result payload.",
    )
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
    evidence_ids: list[str] = Field(default_factory=list)
    evidence_added: list[str] = Field(default_factory=list)
    evidence_removed: list[str] = Field(default_factory=list)
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
    review_changes: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)
