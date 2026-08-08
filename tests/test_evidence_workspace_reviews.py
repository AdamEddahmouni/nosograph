import sqlite3
from datetime import datetime, timezone
from io import BytesIO
from zipfile import ZipFile

from fastapi.testclient import TestClient

from med_research.pipeline.evidence_workspace.schemas import (
    Claim,
    EvidenceDossier,
    EvidenceRecord,
    RankedCandidate,
    ResearchRequest,
)
from med_research.web.services.workspace_store import WorkspaceRunStore


def _dossier(run_id: str, score: float, evidence_id: str = "pmid-1") -> EvidenceDossier:
    return EvidenceDossier(
        run_id=run_id,
        request=ResearchRequest(question="Which JAK intervention merits investigation?"),
        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        completed_at=datetime(2026, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
        evidence=[
            EvidenceRecord(
                evidence_id=evidence_id,
                source="pubmed",
                native_id=evidence_id,
                title="JAK intervention study",
                url="https://pubmed.ncbi.nlm.nih.gov/123/",
                snippet="Study evidence",
            )
        ],
        claims=[
            Claim(
                claim_id=f"claim-{run_id}",
                subject_id="tofacitinib",
                subject_type="drug",
                subject_name="Tofacitinib",
                relationship="supports",
                text="The study supports further investigation.",
                evidence_ids=[evidence_id],
                confidence=0.8,
                extraction_method="rules",
            )
        ],
        drug_rankings=[
            RankedCandidate(
                candidate_id="tofacitinib",
                candidate_type="drug",
                name="Tofacitinib",
                score=score,
                confidence_band="moderate",
                explanation="Evidence-backed candidate",
                supporting_claim_ids=[f"claim-{run_id}"],
            )
        ],
        manifest={"provenance": {"fingerprint": f"fingerprint-{run_id}"}},
    )


def _save(store: WorkspaceRunStore, dossier: EvidenceDossier) -> None:
    store.create_run(dossier.run_id, dossier.request)
    store.save_success(dossier, "<html />")


def test_reviews_are_versioned_and_keep_provenance(tmp_path):
    store = WorkspaceRunStore(tmp_path / "workspace.sqlite3")
    _save(store, _dossier("ew-review", 82.0))

    first = store.upsert_review(
        "ew-review",
        "tofacitinib",
        "drug",
        "Tofacitinib",
        "pinned",
        "Strong mechanistic rationale",
        "Follow up with safety review",
        ["follow-up", "mechanism"],
        "A new supporting trial increased confidence.",
        "fingerprint-ew-review",
    )
    second = store.upsert_review(
        "ew-review",
        "tofacitinib",
        "drug",
        "Tofacitinib",
        "rejected",
        "Safety concern",
        "Do not prioritize",
        ["safety"],
        "The safety signal changed my mind.",
        "fingerprint-ew-review",
    )

    assert first["decision"] == "pinned"
    assert second["decision"] == "rejected"
    assert second["tags"] == ["safety"]
    assert second["provenance_fingerprint"] == "fingerprint-ew-review"
    assert len(store.list_reviews("ew-review")) == 1

    with store._connect() as connection:
        events = connection.execute(
            "SELECT previous_decision, decision, changed_my_mind FROM workspace_review_events "
            "WHERE run_id=? ORDER BY event_id",
            ("ew-review",),
        ).fetchall()
    assert [(row[0], row[1]) for row in events] == [
        ("unreviewed", "pinned"),
        ("pinned", "rejected"),
    ]
    assert events[1][2] == "The safety signal changed my mind."


def test_reviews_are_isolated_by_researcher(tmp_path):
    store = WorkspaceRunStore(tmp_path / "workspace.sqlite3")
    _save(store, _dossier("ew-owned", 82.0))

    store.upsert_review(
        "ew-owned",
        "tofacitinib",
        "drug",
        "Tofacitinib",
        "pinned",
        "Alice rationale",
        "Alice notes",
        ["alice"],
        "Alice changed her mind",
        "fp-owned",
        researcher_id="alice",
    )
    store.upsert_review(
        "ew-owned",
        "tofacitinib",
        "drug",
        "Tofacitinib",
        "rejected",
        "Bob rationale",
        "Bob notes",
        ["bob"],
        "Bob changed his mind",
        "fp-owned",
        researcher_id="bob",
    )

    assert store.list_reviews("ew-owned", "alice")[0]["decision"] == "pinned"
    assert store.list_reviews("ew-owned", "bob")[0]["decision"] == "rejected"
    assert store.list_reviews("ew-owned", "anonymous") == []
    assert {event["researcher_id"] for event in store.list_review_events("ew-owned", "alice")} == {
        "alice"
    }


def test_pre_identity_review_tables_migrate_to_anonymous_owner(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE workspace_reviews (
                run_id TEXT NOT NULL, candidate_id TEXT NOT NULL, candidate_type TEXT NOT NULL,
                candidate_name TEXT NOT NULL DEFAULT '', decision TEXT NOT NULL DEFAULT 'unreviewed',
                rationale TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '',
                tags_json TEXT NOT NULL DEFAULT '[]', changed_my_mind TEXT NOT NULL DEFAULT '',
                provenance_fingerprint TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY (run_id, candidate_type, candidate_id)
            );
            CREATE TABLE workspace_review_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
                candidate_id TEXT NOT NULL, candidate_type TEXT NOT NULL,
                previous_decision TEXT NOT NULL, decision TEXT NOT NULL,
                rationale TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '',
                tags_json TEXT NOT NULL DEFAULT '[]', changed_my_mind TEXT NOT NULL DEFAULT '',
                provenance_fingerprint TEXT NOT NULL DEFAULT '', recorded_at TEXT NOT NULL
            );
            INSERT INTO workspace_reviews VALUES
              ('ew-legacy', 'tofacitinib', 'drug', 'Tofacitinib', 'pinned', 'old', '', '[]', '', 'fp', 'now', 'now');
            INSERT INTO workspace_review_events
              (run_id, candidate_id, candidate_type, previous_decision, decision, recorded_at)
              VALUES ('ew-legacy', 'tofacitinib', 'drug', 'unreviewed', 'pinned', 'now');
            """
        )

    store = WorkspaceRunStore(path)
    assert store.list_reviews("ew-legacy", "anonymous")[0]["decision"] == "pinned"
    assert store.list_review_events("ew-legacy", "anonymous")[0]["researcher_id"] == "anonymous"


def test_candidate_history_and_compare_include_evidence_and_review_changes(tmp_path):
    store = WorkspaceRunStore(tmp_path / "workspace.sqlite3")
    _save(store, _dossier("ew-old", 70.0, "pmid-old"))
    newer = _dossier("ew-new", 85.0, "pmid-new")
    newer.completed_at = datetime(2026, 1, 2, tzinfo=timezone.utc)
    _save(store, newer)
    store.upsert_review(
        "ew-old", "tofacitinib", "drug", "Tofacitinib", "pinned", "Old rationale", "", [], "", "fp-old"
    )
    store.upsert_review(
        "ew-new", "tofacitinib", "drug", "Tofacitinib", "rejected", "New rationale", "", [], "Changed my mind", "fp-new"
    )

    history = store.candidate_history("tofacitinib", "drug", "sle")
    assert [point["run_id"] for point in history["points"]] == ["ew-old", "ew-new"]
    assert history["points"][1]["evidence_added"] == ["pmid-new"]
    assert history["points"][1]["evidence_removed"] == ["pmid-old"]
    comparison = store.compare_runs("ew-old", "ew-new")
    assert comparison["drug_changes"][0]["left_evidence_ids"] == ["pmid-old"]
    assert comparison["drug_changes"][0]["right_evidence_ids"] == ["pmid-new"]
    assert comparison["review_changes"][0]["left"]["decision"] == "pinned"
    assert comparison["review_changes"][0]["right"]["decision"] == "rejected"


def test_review_bundle_contains_machine_and_citation_ready_artifacts(tmp_path):
    store = WorkspaceRunStore(tmp_path / "workspace.sqlite3")
    _save(store, _dossier("ew-bundle", 82.0))
    store.upsert_review(
        "ew-bundle", "tofacitinib", "drug", "Tofacitinib", "pinned", "Investigate", "Next step", ["priority"], "", "fp-bundle"
    )
    from med_research.web.services.review_export import build_review_bundle

    archive = build_review_bundle(
        store.get_run("ew-bundle"),
        store.list_reviews("ew-bundle"),
        store.list_review_events("ew-bundle"),
    )
    with ZipFile(BytesIO(archive.getvalue())) as bundle:
        assert set(bundle.namelist()) == {
            "review.md",
            "citations.csv",
            "dossier.json",
            "reviews.json",
            "review-events.json",
            "provenance.json",
        }
        markdown = bundle.read("review.md").decode()
        assert "What changed my mind" in markdown
        assert "Investigate" in markdown
        assert "fingerprint-ew-bundle" in bundle.read("provenance.json").decode()
        assert "pinned" in bundle.read("review-events.json").decode()
        assert "pmid-1" in bundle.read("citations.csv").decode()


def test_review_api_validates_candidates_and_exports_bundle(monkeypatch, tmp_path):
    import med_research.web.routers.workspace as workspace_router

    db_path = tmp_path / "workspace.sqlite3"
    store = WorkspaceRunStore(db_path)
    _save(store, _dossier("ew-api", 82.0))
    monkeypatch.setattr(workspace_router, "WORKSPACE_DB_PATH", db_path)

    from med_research.web.main import app

    with TestClient(app) as client:
        saved = client.put(
            "/api/workspace/runs/ew-api/reviews",
            json={
                "candidate_id": "tofacitinib",
                "candidate_type": "drug",
                "decision": "pinned",
                "rationale": "Promising",
                "notes": "Review safety",
                "tags": ["priority"],
                "changed_my_mind": "The new trial shifted my view.",
            },
            headers={"X-Researcher-ID": "alice"},
        )
        reviews = client.get(
            "/api/workspace/runs/ew-api/reviews", headers={"X-Researcher-ID": "alice"}
        )
        bob_reviews = client.get(
            "/api/workspace/runs/ew-api/reviews", headers={"X-Researcher-ID": "bob"}
        )
        alice_events = client.get(
            "/api/workspace/runs/ew-api/review-events", headers={"X-Researcher-ID": "alice"}
        )
        history = client.get(
            "/api/workspace/candidate-history?candidate_id=tofacitinib&candidate_type=drug&disease_id=sle",
            headers={"X-Researcher-ID": "alice"},
        )
        invalid = client.put(
            "/api/workspace/runs/ew-api/reviews",
            json={"candidate_id": "missing", "candidate_type": "drug", "decision": "pinned"},
        )
        invalid_identity = client.get(
            "/api/workspace/runs/ew-api/reviews",
            headers={"X-Researcher-ID": "not a valid identity"},
        )
        bundle = client.get(
            "/api/workspace/runs/ew-api/review-bundle",
            headers={"X-Researcher-ID": "alice"},
        )

    assert saved.status_code == 200
    assert saved.json()["provenance_fingerprint"] == "fingerprint-ew-api"
    assert reviews.json()["reviews"][0]["decision"] == "pinned"
    assert reviews.json()["reviews"][0]["researcher_id"] == "alice"
    assert bob_reviews.json()["reviews"] == []
    assert alice_events.json()["events"][0]["researcher_id"] == "alice"
    assert history.status_code == 200
    assert history.json()["points"][0]["evidence_ids"] == ["pmid-1"]
    assert invalid.status_code == 404
    assert invalid_identity.status_code == 400
    assert bundle.status_code == 200
    assert bundle.headers["content-type"].startswith("application/zip")
