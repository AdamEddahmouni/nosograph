from pathlib import Path

ROOT = Path("src/med_research/web/static")


def test_condition_comparison_section_present() -> None:
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert 'id="condition-comparison"' in html
    assert 'id="comparison-condition-curies"' in html
    assert "Select 2–5 imported conditions" in html
    assert 'value="pathway"' in html
    assert (
        'value="mechanism"'
        not in html[
            html.index('id="condition-comparison"') : html.index('id="multi-disease-comparison"')
        ]
    )


def test_condition_comparison_functions_present() -> None:
    js = (ROOT / "js" / "dashboard.js").read_text(encoding="utf-8")
    assert "function compareConditions" in js
    assert "function renderNosoGraphCompareResult" in js
    assert "function initConditionCurieTomSelect" in js
    assert "/api/v1/nosograph/comparisons" in js
    assert "maxItems: 5" in js
    assert "claim_id=" in js
    assert "/exports/json" in js
    assert "/exports/markdown" in js


def test_condition_comparison_renders_product_panels_and_explicit_states() -> None:
    js = (ROOT / "js" / "dashboard.js").read_text(encoding="utf-8")
    block = js[js.find("function renderNosoGraphCompareResult") :]
    for label in ("Shared", "Distinct", "Missing data", "KNOWN_ABSENT", "NOT_RECORDED"):
        assert label in block
    assert 'role="tablist"' in block
    assert 'role="tabpanel"' in block


def test_condition_comparison_panels_and_coverage_table_are_accessible() -> None:
    js = (ROOT / "js" / "dashboard.js").read_text(encoding="utf-8")
    block = js[js.find("function renderComparisonDimensionPanel") :]
    css = (ROOT / "css" / "dashboard.css").read_text(encoding="utf-8")

    assert "condition-comparison-shared-heading-" in block
    assert "condition-comparison-distinct-heading-" in block
    assert "condition-comparison-missing-heading-" in block
    assert 'aria-labelledby="condition-comparison-' in block
    assert '<h3 id="condition-comparison-' in block
    assert block.count('scope="col"') == 6
    assert "condition-comparison-number" in block
    assert ".condition-comparison-number" in css
    assert "font-variant-numeric: tabular-nums" in css


def test_condition_comparison_renders_research_disclaimer() -> None:
    js = (ROOT / "js" / "dashboard.js").read_text(encoding="utf-8")
    block = js[js.find("function renderNosoGraphCompareResult") :]
    assert "research" in block.lower()
    assert "condition-comparison-disclaimer" in block
