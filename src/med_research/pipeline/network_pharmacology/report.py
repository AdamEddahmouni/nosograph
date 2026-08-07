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

from med_research.pipeline.reporting import apply_disease_labels


def generate_html_report(results: dict, disease_id: str = "sle") -> str:
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

    # ── Assemble via template ──────────────────────────────────────
    from med_research.templates import env as template_env

    html = template_env.get_template("reports/network_pharmacology.html").render(
        ctx_0=gm["n_nodes"],
        ctx_1=gm["n_edges"],
        ctx_2=datetime.now().strftime("%B %d, %Y at %H:%M"),
        ctx_3=metrics_html,
        ctx_4=f"{com.get('modularity', 0):.3f}",
        ctx_5=com_rows,
        ctx_6=bridge_rows,
        ctx_7=centrality_sections,
    )
    html = apply_disease_labels(html, disease_id)

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
