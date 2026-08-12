from pathlib import Path

ROOT = Path("src/med_research/web/static")


def test_condition_comparison_section_present() -> None:
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert 'id="condition-comparison"' in html
    assert "condition-comparison" in html


def test_condition_comparison_functions_present() -> None:
    js = (ROOT / "js" / "dashboard.js").read_text(encoding="utf-8")
    assert "function compareConditions" in js
    assert "function renderComparisonResult" in js
    assert "function initConditionCurieTomSelect" in js


def test_condition_comparison_renders_research_disclaimer() -> None:
    js = (ROOT / "js" / "dashboard.js").read_text(encoding="utf-8")
    block = js[js.find("function renderComparisonResult") :]
    assert "research" in block.lower()
    assert "condition-comparison-disclaimer" in block
