from pathlib import Path

ROOT = Path("src/med_research/web/static")


def test_condition_explorer_section_present() -> None:
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert 'id="condition-explorer"' in html
    assert "condition-explorer" in html


def test_condition_explorer_functions_present() -> None:
    js = (ROOT / "js" / "dashboard.js").read_text(encoding="utf-8")
    assert "function searchConditions" in js
    assert "function renderConditionExplorer" in js
    assert "function renderClaimEvidence" in js
    assert "function loadBiomedImportStatus" in js
    assert "function handleUniversalDeepLinks" in js


def test_condition_explorer_renders_research_disclaimer() -> None:
    js = (ROOT / "js" / "dashboard.js").read_text(encoding="utf-8")
    assert "research" in js.lower()
    assert "condition-explorer-disclaimer" in js


def test_condition_explorer_escapes_html() -> None:
    js = (ROOT / "js" / "dashboard.js").read_text(encoding="utf-8")
    explorer_block = js[js.find("function renderConditionExplorer") :]
    assert "escapeHtml(" in explorer_block
