"""Semantic Search HTML Report Generator."""

from datetime import datetime
from pathlib import Path

from med_research.templates import env as template_env


def escape_html(value):
    if value is None:
        return ""
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def generate_semantic_report(results: list, query: str, indexed_count: int) -> str:
    """Generate semantic search results report."""
    html = template_env.get_template("reports/semantic_search.html").render(
        results=results,
        query=query,
        indexed_count=indexed_count,
        n_results=len(results),
        generated_at=datetime.now().strftime("%B %d, %Y at %H:%M"),
    )

    report_path = Path(__file__).parent / "report.html"
    report_path.write_text(html, encoding="utf-8")
    return str(report_path)
