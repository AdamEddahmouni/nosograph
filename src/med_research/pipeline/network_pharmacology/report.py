"""
Network Pharmacology Report Generator

Generates a standalone HTML report with:
  - Graph-level metrics summary
  - Community detection visualization
  - Centrality rankings (degree, betweenness, eigenvector, PageRank)
  - Bridge node analysis
"""

from datetime import datetime
from pathlib import Path


def generate_html_report(results: dict) -> str:
    """Generate a standalone HTML report and return the path."""

    output_path = Path(__file__).parent / "report.html"

    gm = results["graph_metrics"]
    com = results.get("communities", {})
    bridges = results.get("bridge_nodes", [])
    centrality = results.get("centrality", {})

    # Graph metrics stats
    metrics_html = f"""        <div class="stat-card">
            <div class="stat-value" style="color:#4ade80;">{gm['n_nodes']}</div>
            <div class="stat-label">Total Nodes</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" style="color:#818cf8;">{gm['n_edges']}</div>
            <div class="stat-label">Total Edges</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" style="color:#fbbf24;">{gm['density']:.3f}</div>
            <div class="stat-label">Graph Density</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" style="color:#c084fc;">{gm['diameter']}</div>
            <div class="stat-label">Diameter</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" style="color:#22d3ee;">{gm['avg_shortest_path']:.2f}</div>
            <div class="stat-label">Avg Shortest Path</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" style="color:#f472b6;">{gm['avg_clustering']:.3f}</div>
            <div class="stat-label">Avg Clustering Coef</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" style="color:#f59e0b;">{gm['n_components']}</div>
            <div class="stat-label">Components</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" style="color:#4ade80;">{gm['assortativity']:.3f}</div>
            <div class="stat-label">Assortativity</div>
        </div>"""

    # Communities table
    com_rows = ""
    if com.get("communities"):
        for c in com["communities"]:
            labels = ", ".join(c["node_labels"][:5])
            if len(c["node_labels"]) > 5:
                labels += f" +{len(c['node_labels']) - 5} more"
            com_rows += f"""        <tr>
            <td>{c['id']}</td>
            <td><strong>{c['dominant_type']}</strong></td>
            <td>{c['size']}</td>
            <td class="muted">{labels}</td>
        </tr>"""

    # Bridge nodes table
    bridge_rows = ""
    for i, b in enumerate(bridges[:15], 1):
        bridge_rows += f"""        <tr>
            <td class="rank">{i}</td>
            <td><strong>{escape_html(b['label'])}</strong></td>
            <td>{b['type']}</td>
            <td style="color:#fbbf24;font-weight:700;">{b['betweenness']:.4f}</td>
        </tr>"""

    # Centrality tabs - top 10 for each
    centrality_sections = ""
    metric_labels = {
        "degree": "Degree Centrality",
        "betweenness": "Betweenness Centrality",
        "eigenvector": "Eigenvector Centrality",
        "closeness": "Closeness Centrality",
        "pagerank": "PageRank",
    }
    for metric, label in metric_labels.items():
        scores = centrality.get(metric, [])
        if not scores:
            continue
        rows = ""
        for i, n in enumerate(scores[:10], 1):
            rows += f"""        <tr>
            <td class="rank">{i}</td>
            <td><strong>{escape_html(n['label'])}</strong></td>
            <td>{n['type']}</td>
            <td style="color:#818cf8;font-weight:700;">{n['score']:.4f}</td>
        </tr>"""
        centrality_sections += f"""        <h3 class="metric-title">{label}</h3>
        <div class="table-container" style="margin-bottom:16px;">
            <table>
                <thead><tr><th>#</th><th>Node</th><th>Type</th><th>Score</th></tr></thead>
                <tbody>{rows}</tbody>
            </table>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Network Pharmacology Report</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            background: #0a0a0f; color: #e0e0e8; line-height: 1.6;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}

        .hero {{
            background: linear-gradient(135deg, #0f1729, #0f1820, #0f1729);
            border: 1px solid #252535; border-radius: 16px;
            padding: 40px; margin-bottom: 32px; text-align: center;
        }}
        .hero h1 {{
            font-size: 2.2rem; font-weight: 800;
            background: linear-gradient(135deg, #22d3ee, #818cf8, #c084fc);
            -webkit-background-clip: text; background-clip: text;
            -webkit-text-fill-color: transparent; margin-bottom: 8px;
        }}
        .hero .subtitle {{ color: #787890; font-size: 1rem; }}
        .hero .date {{ color: #787890; font-size: 0.8rem; margin-top: 8px; }}

        .stats-grid {{
            display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px;
            margin-bottom: 32px;
        }}
        .stat-card {{
            background: #13131a; border: 1px solid #252535;
            border-radius: 12px; padding: 20px; text-align: center;
        }}
        .stat-card .stat-value {{ font-size: 1.7rem; font-weight: 800; margin-bottom: 4px; }}
        .stat-card .stat-label {{ color: #787890; font-size: 0.76rem; }}

        .section-title {{
            font-size: 1.3rem; font-weight: 700; margin: 32px 0 16px;
            padding-bottom: 8px; border-bottom: 1px solid #252535;
        }}
        .metric-title {{
            font-size: 1rem; font-weight: 600; margin: 20px 0 8px;
            color: #a5b4fc;
        }}

        .table-container {{
            overflow-x: auto; background: #13131a;
            border: 1px solid #252535; border-radius: 12px;
        }}
        table {{ width: 100%; border-collapse: collapse; font-size: 0.86rem; }}
        th {{
            text-align: left; padding: 12px 16px; background: #1a1a24;
            color: #787890; font-weight: 600; font-size: 0.73rem;
            text-transform: uppercase; letter-spacing: 0.05em;
            border-bottom: 1px solid #252535;
        }}
        td {{ padding: 10px 16px; border-bottom: 1px solid #1a1a24; }}
        tr:hover td {{ background: rgba(34,211,238,0.02); }}
        .rank {{ font-weight: 700; color: #787890; font-size: 1rem; min-width: 28px; }}
        .muted {{ color: #787890; font-size: 0.78rem; }}

        .methodology {{
            background: #13131a; border: 1px solid #252535;
            border-radius: 12px; padding: 24px; margin-bottom: 32px;
        }}
        .methodology h3 {{ font-size: 1rem; margin-bottom: 12px; }}
        .methodology ul {{ margin-left: 20px; color: #787890; font-size: 0.86rem; }}
        .methodology li {{ margin-bottom: 6px; }}
        .methodology strong {{ color: #e0e0e8; }}

        footer {{ text-align: center; padding: 40px; color: #787890; font-size: 0.78rem; }}
        footer a {{ color: #818cf8; }}

        @media (max-width: 768px) {{
            .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
            .hero {{ padding: 24px; }}
            .hero h1 {{ font-size: 1.4rem; }}
        }}
    </style>
</head>
<body>
    <div class="container">

        <div class="hero">
            <h1>🌐 Network Pharmacology Report</h1>
            <p class="subtitle">Deep Network Analysis of the Lupus Knowledge Graph &mdash; {gm['n_nodes']} Nodes, {gm['n_edges']} Edges</p>
            <p class="date">Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')} | Centrality, Communities, Bridge Nodes</p>
        </div>

        <div class="stats-grid">
            {metrics_html}
        </div>

        <h2 class="section-title">🔗 Community Structure (Modularity: {com.get('modularity', 0):.3f})</h2>
        <div class="table-container" style="margin-bottom:28px;">
            <table>
                <thead><tr><th>#</th><th>Dominant Type</th><th>Size</th><th>Key Members</th></tr></thead>
                <tbody>{com_rows}</tbody>
            </table>
        </div>

        <h2 class="section-title">🌉 Top Bridge Nodes (Betweenness Centrality)</h2>
        <div class="table-container" style="margin-bottom:28px;">
            <table>
                <thead><tr><th>#</th><th>Node</th><th>Type</th><th>Betweenness</th></tr></thead>
                <tbody>{bridge_rows}</tbody>
            </table>
        </div>

        <h2 class="section-title">🎯 Centrality Rankings</h2>
        {centrality_sections}

        <div class="methodology">
            <h3>📐 Methodology</h3>
            <ul>
                <li><strong>Degree Centrality</strong> &mdash; Number of direct connections. High = highly connected hub.</li>
                <li><strong>Betweenness Centrality</strong> &mdash; How often a node lies on shortest paths. High = critical bridge.</li>
                <li><strong>Eigenvector Centrality</strong> &mdash; Connection to other well-connected nodes. High = influential hub.</li>
                <li><strong>Closeness Centrality</strong> &mdash; Short average distance to all other nodes. High = efficient spreader.</li>
                <li><strong>PageRank</strong> &mdash; Importance based on connections from important nodes. High = key network player.</li>
                <li><strong>Community Detection</strong> &mdash; Louvain algorithm identifying naturally clustered subnetworks.</li>
            </ul>
        </div>

        <footer>
            <p>Network Pharmacology Hub &middot; Part of the Lupus Research Platform</p>
            <p><a href="../knowledge_graph/web/index.html">Knowledge Graph</a> &middot; <a href="../drug_repurposing/report.html">Drug Repurposing</a></p>
        </footer>
    </div>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return str(output_path)


def escape_html(text: str) -> str:
    """Escape HTML special characters."""
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
