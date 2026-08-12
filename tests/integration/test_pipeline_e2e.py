"""Offline end-to-end pipeline smoke: KG → repurpose → synergy → safety."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from med_research.pipeline.reporting import disease_context
from tests.cli_helpers import parse_cli_args, run_cli_handler

PROJECT_ROOT = Path(__file__).parent.parent.parent
DISEASES = ("sle", "ra", "ibd")

REPORT_PATHS = {
    "repurpose": PROJECT_ROOT / "src/med_research/pipeline/drug_repurposing/report.html",
    "synergy": PROJECT_ROOT / "src/med_research/pipeline/drug_synergy/report.html",
    "safety": PROJECT_ROOT / "src/med_research/pipeline/adverse_events/report.html",
}

pytestmark = [pytest.mark.integration]




def _assert_disease_report(disease_id: str, html: str) -> None:
    """Assert disease-aware labeling and provenance footer."""
    context = disease_context(disease_id)
    label_candidates = {
        context["name"],
        context["profile_name"],
        context["short_label"],
    }
    if disease_id == "ra":
        label_candidates.add("Rheumatoid Arthritis")
    elif disease_id == "ibd":
        label_candidates.add("Inflammatory Bowel Disease")
    elif disease_id == "sle":
        label_candidates.add("Lupus")
        label_candidates.add("Systemic Lupus Erythematosus")

    assert any(label and label in html for label in label_candidates)
    if disease_id != "sle":
        assert "Systemic Lupus Erythematosus" not in html
    assert "Reproducibility" in html
    assert re.search(r"fingerprint <code>[a-f0-9]{20}</code>", html)


@pytest.mark.parametrize("disease_id", DISEASES)
class TestOfflinePipelineE2E:
    """Run the core offline chain via direct CLI handler imports."""

    def test_kg_export_repurpose_synergy_safety_with_html(self, disease_id):
        from med_research.cli import cmd_kg, cmd_repurpose, cmd_safety, cmd_synergy

        assert run_cli_handler(cmd_kg, "kg", "--disease", disease_id, "--export") == 0
        assert (
            run_cli_handler(
                cmd_repurpose,
                "repurpose",
                "--disease",
                disease_id,
                "--top",
                "5",
                "--export-html",
            )
            == 0
        )
        assert (
            run_cli_handler(
                cmd_synergy,
                "synergy",
                "--disease",
                disease_id,
                "--top",
                "5",
                "--export-html",
            )
            == 0
        )
        assert (
            run_cli_handler(
                cmd_safety,
                "safety",
                "--disease",
                disease_id,
                "--export-html",
            )
            == 0
        )

        for label, path in REPORT_PATHS.items():
            assert path.exists(), f"Missing {label} report at {path}"
            _assert_disease_report(disease_id, path.read_text(encoding="utf-8"))

    def test_repurpose_handler_args_match_parser(self, disease_id):
        """Sanity-check argparse wiring for the repurpose step."""
        args = parse_cli_args("repurpose", "--disease", disease_id, "--top", "3", "--export-html")
        assert args.disease == disease_id
        assert args.top == 3
        assert args.export_html is True
