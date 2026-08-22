from __future__ import annotations

from pathlib import Path

from med_research.biomed.nosograph_compare.service import NosoGraphCompareService
from med_research.web.services.nosograph_compare_export import render_json, render_markdown
from med_research.web.services.nosograph_compare_service import to_compare_v2_view

CONDITIONS = ("MONDO:0000001", "MONDO:0000002", "MONDO:0000003")
GOLDEN = Path("tests/fixtures/golden")


def test_compare_exports_match_byte_stable_golden_files(compare_v2_repository) -> None:
    result = NosoGraphCompareService(compare_v2_repository).compare_many(list(CONDITIONS))
    view = to_compare_v2_view(result)

    json_export = render_json(view)
    markdown_export = render_markdown(view)

    assert json_export == (GOLDEN / "nosograph_compare_v2_export.json").read_bytes()
    assert markdown_export == (GOLDEN / "nosograph_compare_v2_export.md").read_bytes()
    assert b"- **Result schema:** `2.0`" in markdown_export
    assert json_export.endswith(b"\n") and not json_export.endswith(b"\n\n")
    assert markdown_export.endswith(b"\n") and not markdown_export.endswith(b"\n\n")


def test_compare_markdown_escapes_labels_and_remains_single_line(compare_v2_repository) -> None:
    result = NosoGraphCompareService(compare_v2_repository).compare_many(
        list(CONDITIONS), dimensions=["phenotype"]
    )
    view = to_compare_v2_view(result)
    labels = dict(view.condition_labels)
    labels[CONDITIONS[0]] = "Condition | One\n#review"

    markdown = render_markdown(view.model_copy(update={"condition_labels": labels})).decode()

    assert "Condition \\| One \\#review" in markdown
    assert "created_at" not in markdown
    assert "updated_at" not in markdown
