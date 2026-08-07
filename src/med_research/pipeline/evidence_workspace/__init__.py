"""SLE-first Evidence-to-Hypothesis Workspace."""

from .schemas import (
    Citation,
    Claim,
    EvidenceDossier,
    EvidenceRecord,
    GraphExplanation,
    RankedCandidate,
    ResearchRequest,
    SourceStatus,
    deduplicate_evidence,
    normalize_request,
)
from .sources import FDALabelSource, GWASSource
from .workspace import build_search_terms, run_workspace

__all__ = [
    "Citation",
    "Claim",
    "EvidenceDossier",
    "FDALabelSource",
    "GWASSource",
    "EvidenceRecord",
    "GraphExplanation",
    "RankedCandidate",
    "ResearchRequest",
    "SourceStatus",
    "build_search_terms",
    "deduplicate_evidence",
    "normalize_request",
    "run_workspace",
]
