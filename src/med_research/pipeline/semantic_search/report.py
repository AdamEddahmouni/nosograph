"""Semantic Search HTML Report Generator."""

from datetime import datetime
from pathlib import Path


def escape_html(value):
    if value is None:
        return ""
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def generate_semantic_report(results: list, query: str, indexed_count: int) -> str:
    """Generate semantic search results report."""
    now = datetime.now().strftime("%B %d, %Y at %H:%M")
    n = len(results)

    # Results table
    table_rows = ""
    for r in results:
        sim_color = "#4ade80" if r["similarity"] >= 8.0 else ("#fbbf24" if r["similarity"] >= 6.0 else "#f87171")
        table_rows += f"""
            <tr>
                <td class="col-rank">#{r['rank']}</td>
                <td class="col-title">{escape_html(r.get('title', '')[:120])}</td>
                <td class="col-score" style="color:{sim_color}">{r['similarity']:.1f}</td>
                <td class="col-year">{r.get('year', '-')}</td>
                <td class="col-journal">{escape_html(r.get('journal', '')[:50])}</td>
            </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Semantic Search Report</title>
    <style>
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0a0a1a; color: #e2e8f0; line-height: 1.6; min-height: 100vh; }}
        .container {{ max-width: 1100px; margin: 0 auto; padding: 24px; }}
        .hero {{ text-align: center; padding: 48px 24px 32px; background: linear-gradient(135deg, rgba(99,102,241,0.15), rgba(59,130,246,0.1), rgba(34,211,238,0.08)); border-radius: 16px; margin-bottom: 32px; }}
        .hero h1 {{ font-size: 2.2rem; font-weight: 800; margin-bottom: 8px; }}
        .hero .subtitle {{ color: #94a3b8; font-size: 1rem; }}
        .hero .date {{ color: #64748b; font-size: 0.82rem; margin-top: 8px; }}
        .query-box {{ background: rgba(30,30,50,0.8); border: 1px solid rgba(99,102,241,0.3); border-radius: 12px; padding: 16px 20px; margin-bottom: 24px; font-family: monospace; color: #818cf8; font-size: 1rem; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px; margin-bottom: 32px; }}
        .stat-card {{ background: rgba(30,30,50,0.8); border: 1px solid rgba(100,100,150,0.2); border-radius: 12px; padding: 20px; text-align: center; }}
        .stat-value {{ font-size: 2rem; font-weight: 800; }}
        .stat-label {{ color: #94a3b8; font-size: 0.8rem; margin-top: 4px; }}
        .section-title {{ font-size: 1.4rem; font-weight: 700; margin: 32px 0 16px; padding-bottom: 8px; border-bottom: 1px solid rgba(100,100,150,0.2); }}
        table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; background: rgba(30,30,50,0.6); border-radius: 12px; overflow: hidden; }}
        th {{ background: rgba(50,50,70,0.8); padding: 12px 10px; text-align: left; font-weight: 600; color: #94a3b8; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.05em; }}
        td {{ padding: 10px; border-bottom: 1px solid rgba(100,100,150,0.1); }}
        tr:hover {{ background: rgba(100,100,150,0.08); }}
        .col-rank {{ width: 50px; color: #64748b; text-align: center; }}
        .col-title {{ font-weight: 600; }}
        .col-score {{ font-weight: 700; text-align: center; width: 70px; }}
        .col-year {{ text-align: center; width: 60px; }}
        .col-journal {{ color: #94a3b8; font-size: 0.78rem; width: 140px; }}
        .methodology {{ background: rgba(30,30,50,0.6); border: 1px solid rgba(100,100,150,0.2); border-radius: 12px; padding: 24px; margin: 32px 0; }}
        .methodology h3 {{ margin-bottom: 12px; }}
        .methodology p {{ color: #94a3b8; margin-bottom: 8px; }}
        .methodology ul {{ padding-left: 20px; color: #94a3b8; }}
        .methodology li {{ margin-bottom: 6px; }}
        .empty-state {{ text-align: center; padding: 48px 24px; color: #64748b; }}
        footer {{ text-align: center; padding: 32px 0; color: #64748b; font-size: 0.8rem; border-top: 1px solid rgba(100,100,150,0.1); margin-top: 32px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="hero">
            <h1>🧠 Semantic Literature Search</h1>
            <p class="subtitle">Embedding-Based PubMed Search — Find Papers by Meaning, Not Keywords</p>
            <p class="date">Generated: {now}</p>
        </div>

        <div class="query-box">🔍 Query: {escape_html(query) if query else '(index only — no query executed)'}</div>

        <div class="stats-grid">
            <div class="stat-card"><div class="stat-value" style="color:#818cf8;">{indexed_count}</div><div class="stat-label">Articles Indexed</div></div>
            <div class="stat-card"><div class="stat-value" style="color:#4ade80;">{n}</div><div class="stat-label">Search Results</div></div>
            <div class="stat-card"><div class="stat-value" style="color:#a78bfa;">all-MiniLM</div><div class="stat-label">Embedding Model</div></div>
            <div class="stat-card"><div class="stat-value" style="color:#22d3ee;">384</div><div class="stat-label">Embedding Dims</div></div>
        </div>

        <h2 class="section-title">📄 Search Results</h2>
        {"<table><thead><tr><th>#</th><th>Title</th><th>Sim</th><th>Year</th><th>Journal</th></tr></thead><tbody>" + table_rows + "</tbody></table>" if results else '<div class="empty-state"><p>No results yet. Run a search query or index articles first.</p></div>'}

        <div class="methodology">
            <h3>🔬 How Semantic Search Works</h3>
            <p>Traditional PubMed queries use <strong>keyword + MeSH terms</strong>. This means a query for "drugs that suppress type I interferon" would miss papers about "JAK-STAT inhibition" or "TLR7/9 blockade" unless those exact phrases appear.</p>
            <p style="margin-top:12px;">Semantic search uses <strong>sentence-transformers embeddings</strong> to understand meaning:</p>
            <ul>
                <li><strong style="color:#818cf8;">all-MiniLM-L6-v2</strong> — 384-dimensional embeddings, 80MB model, runs locally</li>
                <li><strong style="color:#22d3ee;">ChromaDB</strong> — vector database for fast similarity search</li>
                <li><strong style="color:#4ade80;">Cosine Similarity</strong> — scores 0-10 based on semantic closeness</li>
            </ul>
            <p style="margin-top:12px;font-size:0.82rem;">Example: Searching "B cell depletion therapy lupus" finds papers about rituximab, obinutuzumab, CD19 CAR-T, and BAFF inhibition — even when those exact terms aren't in the paper title or abstract.</p>
        </div>

        <footer><p>Lupus Research Platform · Semantic Search Module (Phase 16)</p><p>⚠️ Computational predictions requiring clinical validation. Not medical advice.</p></footer>
    </div>
</body>
</html>"""

    report_path = Path(__file__).parent / "report.html"
    report_path.write_text(html, encoding="utf-8")
    return str(report_path)
