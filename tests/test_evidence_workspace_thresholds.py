from datetime import datetime, timezone

from med_research.pipeline.evidence_workspace.schemas import RankedCandidate
from med_research.web.services.workspace_store import WorkspaceRunStore

from .test_evidence_workspace_reviews import _dossier, _save


def test_score_and_quality_thresholds_trigger_without_new_evidence(tmp_path):
    store = WorkspaceRunStore(tmp_path / "workspace.sqlite3")
    old = _dossier("ew-threshold-old", 90.0, "pmid-same")
    new = _dossier("ew-threshold-new", 72.0, "pmid-same")
    old.completed_at = datetime(2026, 4, 1, tzinfo=timezone.utc)
    new.completed_at = datetime(2026, 4, 2, tzinfo=timezone.utc)
    old.evidence[0] = old.evidence[0].model_copy(update={"quality_score": 0.9})
    new.evidence[0] = new.evidence[0].model_copy(update={"quality_score": 0.5})
    _save(store, old)
    _save(store, new)
    store.upsert_review(
        "ew-threshold-old",
        "tofacitinib",
        "drug",
        "Tofacitinib",
        "pinned",
        "Follow up",
        "",
        [],
        "",
        "fp-threshold",
        researcher_id="alice",
    )
    store.save_notification_settings(
        "alice",
        "",
        False,
        "",
        False,
        score_drop_threshold=10.0,
        evidence_quality_change_threshold=0.2,
    )

    assert store.refresh_alerts("alice") == 1
    alert = store.list_alerts("alice")["alerts"][0]
    assert alert["evidence_added"] == []
    assert alert["score_drop"] == 18.0
    assert alert["previous_quality"] == 0.9
    assert alert["current_quality"] == 0.5
    assert alert["quality_change"] == -0.4
    assert set(alert["trigger_reasons"]) == {"score_drop", "evidence_quality_change"}
    assert "score drop" in alert["message"]


def test_rank_threshold_triggers_when_candidate_moves(tmp_path):
    store = WorkspaceRunStore(tmp_path / "workspace.sqlite3")
    old = _dossier("ew-rank-old", 80.0, "pmid-same")
    new = _dossier("ew-rank-new", 80.0, "pmid-same")
    old.completed_at = datetime(2026, 5, 1, tzinfo=timezone.utc)
    new.completed_at = datetime(2026, 5, 2, tzinfo=timezone.utc)
    other = RankedCandidate(
        candidate_id="baricitinib",
        candidate_type="drug",
        name="Baricitinib",
        score=75.0,
        confidence_band="moderate",
        explanation="Comparator",
    )
    old.drug_rankings.append(other)
    new.drug_rankings.insert(0, other.model_copy(update={"score": 85.0}))
    _save(store, old)
    _save(store, new)
    store.upsert_review(
        "ew-rank-old",
        "tofacitinib",
        "drug",
        "Tofacitinib",
        "rejected",
        "Review later",
        "",
        [],
        "",
        "fp-rank",
        researcher_id="alice",
    )
    store.save_notification_settings(
        "alice", "", False, "", False, rank_change_threshold=1
    )

    assert store.refresh_alerts("alice") == 1
    alert = store.list_alerts("alice")["alerts"][0]
    assert alert["evidence_added"] == []
    assert alert["previous_rank"] == 1
    assert alert["current_rank"] == 2
    assert alert["rank_change"] == 1
    assert alert["trigger_reasons"] == ["rank_change"]
