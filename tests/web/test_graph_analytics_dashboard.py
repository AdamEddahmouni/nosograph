"""Integration tests for Graph Analytics UI dashboard elements and contracts."""

from __future__ import annotations

from pathlib import Path

STATIC_DIR = Path("src/med_research/web/static")


def test_dashboard_html_contains_graph_analytics_tab() -> None:
    html_path = STATIC_DIR / "index.html"
    assert html_path.exists()
    content = html_path.read_text(encoding="utf-8")

    # Nav link and hero action button
    assert 'data-nav="graph-analytics"' in content
    assert 'href="#graph-analytics"' in content
    assert "Graph Analytics" in content

    # Section IDs and containers
    assert 'id="graph-analytics"' in content
    assert 'id="path-start-curie"' in content
    assert 'id="path-target-curie"' in content
    assert 'id="path-max-depth"' in content
    assert 'id="pathways-run-btn"' in content
    assert 'id="pathways-result"' in content

    # Target vulnerability ranking section
    assert 'id="target-rank-disease"' in content
    assert 'id="target-rank-top-k"' in content
    assert 'id="target-rank-run-btn"' in content
    assert 'id="target-rank-result"' in content


def test_dashboard_js_contains_analytics_handlers() -> None:
    js_path = STATIC_DIR / "js" / "dashboard.js"
    assert js_path.exists()
    content = js_path.read_text(encoding="utf-8")

    assert "fetchGraphPathways" in content
    assert "renderGraphPathways" in content
    assert "fetchTargetPrioritization" in content
    assert "renderTargetPrioritization" in content
    assert "initGraphAnalytics" in content
