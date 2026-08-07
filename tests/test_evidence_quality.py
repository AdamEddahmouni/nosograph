from datetime import date, datetime, timezone
from pathlib import Path

from med_research.pipeline.evidence_workspace.ranking import rank_drugs
from med_research.pipeline.evidence_workspace.report import render_html
from med_research.pipeline.evidence_workspace.schemas import (
    Claim,
    EvidenceDossier,
    EvidenceRecord,
    ResearchRequest,
)


def _record(source: str, evidence_type: str, evidence_id: str) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        source=source,
        native_id=evidence_id,
        title=f"{evidence_type} evidence",
        url=f"https://example.org/{evidence_id}",
        published_date=date(2025, 1, 1),
        evidence_type=evidence_type,
    )


def _claim(evidence_id: str, candidate_id: str) -> Claim:
    return Claim(
        claim_id=f"claim:{evidence_id}",
        subject_id=candidate_id,
        subject_type="drug",
        subject_name=candidate_id,
        relationship="supports",
        text="Evidence supports the candidate.",
        evidence_ids=[evidence_id],
        confidence=0.8,
        extraction_method="rules",
    )


def test_evidence_records_receive_transparent_quality_tiers():
    regulatory = _record("fda_labels", "label", "spl-1")
    randomized = _record("clinical_trials", "randomized controlled trial", "nct-1")
    gwas = _record("gwas", "genome-wide association", "gwas-1")
    preprint = _record("pubmed", "preprint", "pmid-1")

    assert regulatory.quality_tier == "tier_1"
    assert regulatory.quality_score >= 0.85
    assert "regulatory" in regulatory.quality_rationale.lower()
    assert randomized.quality_tier == "tier_1"
    assert gwas.quality_tier == "tier_2"
    assert preprint.quality_tier == "tier_4"
    assert preprint.quality_score < gwas.quality_score


def test_quality_weighting_changes_candidate_score_transparently():
    high = _record("clinical_trials", "phase 3 randomized controlled trial", "nct-high")
    low = _record("pubmed", "preprint", "pmid-low")
    ranked = rank_drugs(
        [high, low],
        [_claim("nct-high", "high-quality"), _claim("pmid-low", "low-quality")],
    )

    high_result = next(item for item in ranked if item.candidate_id == "high-quality")
    low_result = next(item for item in ranked if item.candidate_id == "low-quality")
    assert (
        high_result.component_scores["evidence_quality"]
        > low_result.component_scores["evidence_quality"]
    )
    assert high_result.score > low_result.score
    assert "evidence quality" in high_result.explanation.lower()


def test_report_exposes_quality_methodology_and_record_metadata():
    record = _record("gwas", "genome-wide association", "gwas-1")
    dossier = EvidenceDossier(
        run_id="ew-quality",
        request=ResearchRequest(question="Quality"),
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        evidence=[record],
    )

    page = render_html(dossier)

    assert "Evidence quality" in page
    assert "Tier 2" in page
    assert "genome-wide association" in page
    assert "Quality methodology" in page


def test_dashboard_mentions_quality_controls():
    root = Path(__file__).parents[1] / "src/med_research/web/static"
    script = (root / "js/dashboard.js").read_text(encoding="utf-8")
    assert "quality_score" in script
    assert "quality_tier" in script
    assert "evidence quality" in script.lower()
