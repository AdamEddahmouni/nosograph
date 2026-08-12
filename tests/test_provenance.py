"""Tests for the shared provenance and reproducibility contract."""

from __future__ import annotations

import re

import pytest

from med_research.pipeline.provenance import (
    SCHEMA_VERSION,
    build_provenance,
    reproducibility_fingerprint,
    utc_now_iso,
)

pytestmark = pytest.mark.unit


def test_utc_now_iso_is_explicit_utc():
    value = utc_now_iso()
    assert value.endswith("+00:00") or value.endswith("Z")
    assert re.match(r"\d{4}-\d{2}-\d{2}T", value)


def test_fingerprint_is_stable_for_identical_inputs():
    inputs = {
        "disease_id": "ibd",
        "module": "evidence_workspace",
        "query": "anti-TNF",
        "filters": {"candidate_type": "drugs"},
    }
    assert reproducibility_fingerprint(inputs) == reproducibility_fingerprint(inputs)


def test_fingerprint_excludes_volatile_runtime_fields():
    base = {
        "disease_id": "sle",
        "module": "literature",
        "query": "BTK",
    }
    with_runtime = {
        **base,
        "run_id": "ew-abc",
        "started_at": "2026-01-01T00:00:00+00:00",
        "completed_at": "2026-01-01T00:01:00+00:00",
    }
    assert reproducibility_fingerprint(base) == reproducibility_fingerprint(with_runtime)


def test_build_provenance_includes_required_contract_fields():
    payload = build_provenance(
        disease_id="ra",
        module="evidence_workspace",
        sources=["pubmed", "clinical_trials"],
        query="JAK inhibitor",
        filters={"candidate_type": "drugs", "max_evidence": 25},
        cache_or_live="cache",
        model="gpt-4o-mini",
        scoring={"ranking": "heuristic"},
        run_id="ew-test-run",
        retrieval_times={"pubmed": "2026-08-07T12:00:00+00:00"},
    )
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["run_id"] == "ew-test-run"
    assert payload["disease_id"] == "ra"
    assert payload["module"] == "evidence_workspace"
    assert payload["package_version"]
    assert payload["sources"] == ["clinical_trials", "pubmed"]
    assert payload["query"] == "JAK inhibitor"
    assert payload["filters"]["max_evidence"] == 25
    assert payload["cache_or_live"] == "cache"
    assert payload["model"] == "gpt-4o-mini"
    assert payload["scoring"]["ranking"] == "heuristic"
    assert payload["retrieval_times"]["pubmed"].endswith("+00:00")
    assert len(payload["fingerprint"]) == 20
    assert payload["generated_at"].endswith("+00:00") or payload["generated_at"].endswith("Z")


def test_workspace_dossier_provenance_matches_run_id():
    from med_research.pipeline.evidence_workspace.workspace import run_workspace

    dossier = run_workspace(
        {
            "disease_id": "sle",
            "question": "BTK inhibition",
            "sources": ["pubmed"],
            "enable_llm": False,
        },
        sources={},
    )
    provenance = dossier.manifest["provenance"]
    assert provenance["run_id"] == dossier.run_id
    assert dossier.manifest["fingerprint"] == provenance["fingerprint"]


def test_provenance_footer_html_escapes_values():
    from med_research.pipeline.reporting import provenance_footer_html

    footer = provenance_footer_html(
        {
            "run_id": "run-<script>",
            "fingerprint": 'fp&"x"',
            "generated_at": "<2026>",
            "cache_or_live": "live",
        }
    )
    assert "<script>" not in footer
    assert "&lt;script&gt;" in footer
    assert "fp&amp;&quot;x&quot;" in footer
    assert "&lt;2026&gt;" in footer
    assert "Reproducibility" in footer


def test_workspace_fingerprint_stable_across_runs():
    from med_research.pipeline.evidence_workspace.workspace import run_workspace

    inputs = {
        "disease_id": "sle",
        "question": "BTK inhibition",
        "sources": ["pubmed"],
        "enable_llm": False,
    }
    dossier1 = run_workspace(inputs, sources={})
    dossier2 = run_workspace(inputs, sources={})

    provenance1 = dossier1.manifest["provenance"]
    provenance2 = dossier2.manifest["provenance"]
    assert provenance1["fingerprint"] == provenance2["fingerprint"]
    assert provenance1["run_id"] != provenance2["run_id"]
    assert provenance1["generated_at"] != provenance2["generated_at"]
