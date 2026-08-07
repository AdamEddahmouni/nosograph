"""
Lupus Bioinformatics Report Generator

Generates a standalone HTML report integrating:
  - Pathway enrichment analysis (GSEApy)
  - PPI network & hub protein analysis (STRING)
  - GWAS Catalog annotation & cross-reference
  - Cross-reference with drug repurposing candidates

The report can be generated from individual module results or
as a combined report when all modules have been run.
"""

import base64
import io
import math
import os
from datetime import datetime
from pathlib import Path

from med_research.pipeline.reporting import apply_disease_labels, disease_context
from med_research.templates import env as template_env

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker

    MPL_AVAILABLE = True
except ImportError:
    MPL_AVAILABLE = False


def generate_bioinformatics_report(
    enrichment_results: dict = None,
    gene_list: list = None,
    kg_matches: dict = None,
    hub_scores: list = None,
    ppi_crossref: dict = None,
    ppi_graph: dict = None,
    gwas_results: dict = None,
    gwas_crossref: dict = None,
    disease_id: str = "sle",
) -> str:
    """
    Generate a standalone HTML bioinformatics report.

    Any combination of results can be provided — the report will
    only show sections for available data.
    """
    output_path = Path(__file__).parent / "bioinformatics_report.html"
    context = disease_context(disease_id)

    # ── Enrichment section ───────────────────────────────────────────────
    enrichment_html = ""
    if enrichment_results:
        enrichment_html += _build_enrichment_section(enrichment_results, gene_list)

        if kg_matches:
            enrichment_html += _build_kg_matches_section(kg_matches)

    # ── PPI section ──────────────────────────────────────────────────────
    ppi_html = ""
    if hub_scores:
        ppi_html += _build_ppi_section(hub_scores, ppi_crossref, ppi_graph)

    # ── GWAS section ─────────────────────────────────────────────────────
    gwas_html = ""
    if gwas_results and gwas_crossref:
        gwas_html += _build_gwas_section(gwas_results, gwas_crossref)

    # ── Stats cards ──────────────────────────────────────────────────────
    stats_cards = _build_stats_cards(
        enrichment_results, gene_list, hub_scores, ppi_crossref,
        gwas_results, gwas_crossref,
    )

    # ── Assemble HTML via shared Jinja2 template ──────────────────────────
    html = template_env.get_template("reports/bioinformatics.html").render(
        stats_cards=stats_cards,
        enrichment_html=enrichment_html,
        ppi_html=ppi_html,
        gwas_html=gwas_html,
        generated_at=datetime.now().strftime("%B %d, %Y at %H:%M"),
        ctx_disease=context["name"],
        ctx_disease_id=context["id"],
    )
    html = apply_disease_labels(html, disease_id)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return str(output_path)


# ── Library color map for consistent plotting ────────────────────────────

LIBRARY_COLORS = {
    "GO_Biological_Process_2023": "#4ade80",
    "KEGG_2021_Human": "#f472b6",
    "Reactome_2022": "#818cf8",
    "WikiPathway_2023_Human": "#fbbf24",
}


def _generate_enrichment_dotplot(enrichment_results: dict, max_terms: int = 40) -> str:
    """
    Generate a publication-quality dot plot from enrichment results.

    Each point represents an enriched term:
      - X-axis: -log10(adjusted p-value)
      - Y-axis: Term name (truncated)
      - Color: Gene set library
      - Size: Number of overlapping genes

    Returns a base64-encoded PNG string suitable for <img src="data:image/png;base64,...">.
    Returns empty string if matplotlib is unavailable or no data to plot.
    """
    if not MPL_AVAILABLE:
        return ""

    # Collect all significant terms across libraries
    rows = []
    for library, result in enrichment_results.items():
        for term in result.get("terms", []):
            adj_p = term.get("adj_p_value", 1.0)
            if adj_p <= 0:
                adj_p = 1e-300  # avoid log10(0)
            n_genes = len(term.get("genes", []))
            neg_log_p = -math.log10(adj_p)
            rows.append(
                {
                    "term": term["term"],
                    "library": library,
                    "neg_log_p": neg_log_p,
                    "n_genes": max(n_genes, 1),
                    "adj_p": adj_p,
                }
            )

    if not rows:
        return ""

    # Sort by -log10(p) descending, take top max_terms
    rows.sort(key=lambda r: r["neg_log_p"], reverse=True)
    rows = rows[:max_terms]

    # Reverse so most significant is at top
    rows.reverse()

    # Prepare plot data
    terms = [r["term"][:60] for r in rows]
    neg_log_ps = [r["neg_log_p"] for r in rows]
    sizes = [r["n_genes"] * 35 for r in rows]  # scale for visibility
    colors = [LIBRARY_COLORS.get(r["library"], "#6b7280") for r in rows]

    # Create figure with dark theme
    fig, ax = plt.subplots(figsize=(10, max(6, len(rows) * 0.28)))
    fig.patch.set_facecolor("#0a0a0f")
    ax.set_facecolor("#0a0a0f")

    # Plot
    scatter = ax.scatter(
        neg_log_ps,
        range(len(terms)),
        s=sizes,
        c=colors,
        alpha=0.85,
        edgecolors="#1a1a24",
        linewidth=0.5,
        zorder=3,
    )

    # Style axes
    ax.set_yticks(range(len(terms)))
    ax.set_yticklabels(terms, fontsize=8, color="#e0e0e8")
    ax.set_xlabel("-log₁₀(adjusted P-value)", fontsize=10, color="#787890", fontweight="600")
    ax.xaxis.set_major_locator(ticker.MaxNLocator(6))
    ax.tick_params(axis="x", colors="#787890", labelsize=8)
    ax.tick_params(axis="y", colors="#e0e0e8")

    # Grid
    ax.grid(axis="x", color="#1a1a24", linewidth=0.6, alpha=0.6, zorder=0)
    ax.set_axisbelow(True)

    # Significance threshold line
    sig_line = -math.log10(0.05)
    ax.axvline(x=sig_line, color="#f43f5e", linewidth=1, linestyle="--", alpha=0.5, zorder=1)
    ax.text(
        sig_line + 0.3,
        len(terms) - 1,
        "FDR = 0.05",
        fontsize=7,
        color="#f43f5e",
        alpha=0.7,
        va="top",
    )

    # Spine styling
    for spine in ax.spines.values():
        spine.set_color("#252535")
        spine.set_linewidth(0.8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Legend for libraries
    legend_handles = []
    for lib, color in LIBRARY_COLORS.items():
        label = lib.replace("GO_Biological_Process_2023", "GO BP 2023")
        label = label.replace("KEGG_2021_Human", "KEGG 2021")
        label = label.replace("Reactome_2022", "Reactome 2022")
        label = label.replace("WikiPathway_2023_Human", "WikiPathways 2023")
        legend_handles.append(
            plt.Line2D(
                [0], [0], marker="o", color="w", markerfacecolor=color,
                markersize=8, label=label,
            )
        )

    # Legend for gene count sizes
    size_handles = []
    for n_genes in [2, 5, 10, 15]:
        marker_size = math.sqrt(n_genes * 35)
        size_handles.append(
            plt.Line2D(
                [0], [0], marker="o", color="w",
                markerfacecolor="#787890", markersize=marker_size,
                label=f"{n_genes} genes", alpha=0.6,
            )
        )

    # Library legend (upper right)
    legend1 = ax.legend(
        handles=legend_handles,
        loc="upper right",
        fontsize=7,
        framealpha=0.9,
        facecolor="#13131a",
        edgecolor="#252535",
        labelcolor="#787890",
        borderpad=0.8,
        title="Gene Set Library",
        title_fontsize=7,
    )
    legend1.get_title().set_color("#787890")
    ax.add_artist(legend1)

    # Size legend (lower right)
    legend2 = ax.legend(
        handles=size_handles,
        loc="lower right",
        fontsize=7,
        framealpha=0.9,
        facecolor="#13131a",
        edgecolor="#252535",
        labelcolor="#787890",
        borderpad=0.8,
        title="Gene Count",
        title_fontsize=7,
    )
    legend2.get_title().set_color("#787890")

    # Title
    ax.set_title(
        "Enrichment Dot Plot",
        fontsize=12,
        fontweight="700",
        color="#e0e0e8",
        pad=12,
    )

    plt.tight_layout()

    # Save to base64
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="#0a0a0f")
    plt.close(fig)
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode("utf-8")
    return encoded


def _build_stats_cards(
    enrichment_results, gene_list, hub_scores, ppi_crossref,
    gwas_results, gwas_crossref,
) -> str:
    """Build the stats cards row."""
    cards = ""

    if enrichment_results:
        n_enriched = sum(
            len(r.get("terms", [])) for r in enrichment_results.values()
        )
        n_sig = sum(
            1
            for r in enrichment_results.values()
            for t in r.get("terms", [])
            if t.get("adj_p_value", 1.0) < 0.05
        )
        cards += f"""
            <div class="stat-card">
                <div class="stat-value" style="color:#4ade80;">{n_sig}</div>
                <div class="stat-label">Significant Enriched Pathways</div>
            </div>"""

    if gene_list:
        cards += f"""
            <div class="stat-card">
                <div class="stat-value" style="color:#818cf8;">{len(gene_list)}</div>
                <div class="stat-label">Lupus Genes Analyzed</div>
            </div>"""

    if hub_scores and ppi_crossref:
        n_matched = len(ppi_crossref.get("hub_candidate_matches", []))
        n_untargeted = len(ppi_crossref.get("hub_untargeted", []))
        cards += f"""
            <div class="stat-card">
                <div class="stat-value" style="color:#c084fc;">{n_matched}</div>
                <div class="stat-label">Hub Genes with Candidates</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color:#fbbf24;">{n_untargeted}</div>
                <div class="stat-label">Untargeted Hub Genes</div>
            </div>"""

    if gwas_crossref:
        cards += f"""
            <div class="stat-card">
                <div class="stat-value" style="color:#4ade80;">{gwas_crossref.get('n_validated', 0)}</div>
                <div class="stat-label">GWAS-Validated KG Genes</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color:#fbbf24;">{gwas_crossref.get('n_novel', 0)}</div>
                <div class="stat-label">Novel GWAS Genes</div>
            </div>"""

    if not cards:
        cards = '<div class="stat-card"><div class="stat-value" style="color:#787890;">—</div><div class="stat-label">No data available</div></div>'

    return f'<div class="stats-grid">{cards}</div>'


def _build_enrichment_section(enrichment_results: dict, gene_list: list) -> str:
    """Build the enrichment analysis section."""
    if not gene_list:
        return ""

    gene_str = ", ".join(g["symbol"] for g in gene_list[:10])
    if len(gene_list) > 10:
        gene_str += f" (+{len(gene_list) - 10} more)"

    # Generate enrichment dot plot
    plot_img = ""
    plot_b64 = _generate_enrichment_dotplot(enrichment_results)
    if plot_b64:
        plot_img = f"""
        <div class="enrichment-plot">
            <img src="data:image/png;base64,{plot_b64}"
                 alt="Enrichment Dot Plot"
                 style="width:100%;max-width:900px;border-radius:10px;"
                 loading="lazy">
        </div>"""

    html = f"""
        <h2 class="section-title">📊 Pathway Enrichment Analysis</h2>
        <p class="muted" style="margin-bottom:12px;">
            Gene set enrichment across GO, KEGG, Reactome, and WikiPathways.
            Input: {gene_str}
        </p>
        {plot_img}
        <div class="enrichment-libraries">"""

    for library, result in enrichment_results.items():
        terms = result.get("terms", [])
        if not terms:
            continue

        lib_name = result.get("library", library)
        n_sig = sum(1 for t in terms if t.get("adj_p_value", 1.0) < 0.05)

        terms_html = ""
        for t in terms[:10]:
            p = t.get("adj_p_value", 1.0)
            sig_class = "badge-green" if p < 0.05 else "badge-yellow"
            sig_label = "✓ FDR<0.05" if p < 0.05 else f"P={p:.1e}"
            genes = ", ".join(t.get("genes", [])[:4])

            terms_html += f"""
            <div class="enrichment-term">
                <div class="term-name">
                    <div style="margin-bottom:2px;">{escape_html(t['term'][:80])}</div>
                    <div class="term-genes">{genes}</div>
                </div>
                <div style="text-align:right;">
                    <span class="badge {sig_class}">{sig_label}</span>
                    <div style="font-size:0.72rem;color:#787890;margin-top:2px;">
                        OR={t.get('odds_ratio', 0):.1f}
                    </div>
                </div>
            </div>"""

        html += f"""
            <div class="enrichment-card">
                <div class="enrichment-card-header">
                    <span>{lib_name}</span>
                    <span class="badge badge-cyan">{n_sig} significant</span>
                </div>
                {terms_html}
            </div>"""

    html += "</div>"
    return html


def _build_kg_matches_section(kg_matches: dict) -> str:
    """Build the KG pathway cross-reference section."""
    if not kg_matches:
        return ""

    matches_html = ""
    for key, matches_list in sorted(
        kg_matches.items(),
        key=lambda x: min(m["adj_p_value"] for m in x[1]),
    ):
        best = min(matches_list, key=lambda m: m["adj_p_value"])
        matches_html += f"""
        <div class="match-card">
            <span style="min-width:120px;font-weight:600;">{best['kg_pathway_name'][:40]}</span>
            <span class="match-arrow">↔</span>
            <span style="flex:1;">{best['enrichment_term'][:60]} <span class="muted">({best['library']})</span></span>
            <span class="badge badge-green">P={best['adj_p_value']:.1e}</span>
        </div>"""

    return f"""
        <h2 class="section-title">🔗 Cross-Reference: Enrichment ↔ Knowledge Graph Pathways</h2>
        <p class="muted" style="margin-bottom:12px;">
            Matching enriched terms against the 7 curated lupus pathways in the knowledge graph.
            Validates that enrichment recovers known lupus biology.
        </p>
        {matches_html}
    """


def _generate_ppi_hub_chart(hub_scores: list, ppi_crossref: dict) -> str:
    """
    Generate a hub score bar chart for the PPI network.

    Shows top lupus-gene hub proteins ranked by hub score.

    Returns a base64-encoded PNG string or empty string if matplotlib unavailable.
    """
    if not MPL_AVAILABLE or not hub_scores:
        return ""

    # Filter to lupus gene hubs, take top 15
    lupus_hubs = [h for h in hub_scores if h.get("is_lupus_gene", False)]
    if not lupus_hubs:
        lupus_hubs = hub_scores[:15]
    lupus_hubs = lupus_hubs[:15]
    lupus_hubs.reverse()  # Bottom = lowest, top = highest

    symbols = [h["symbol"] for h in lupus_hubs]
    hub_vals = [h["hub_score"] for h in lupus_hubs]
    degrees = [h.get("degree", 0) for h in lupus_hubs]

    # Check if hub has candidates
    matched_ids = {m["gene_id"] for m in ppi_crossref.get("hub_candidate_matches", [])} if ppi_crossref else set()
    bar_colors = [
        "#4ade80" if h.get("gene_id") in matched_ids else "#818cf8"
        for h in lupus_hubs
    ]

    fig, ax = plt.subplots(figsize=(10, max(5, len(symbols) * 0.35)))
    fig.patch.set_facecolor("#0a0a0f")
    ax.set_facecolor("#0a0a0f")

    bars = ax.barh(range(len(symbols)), hub_vals, color=bar_colors, height=0.6, zorder=2)

    ax.set_yticks(range(len(symbols)))
    ax.set_yticklabels(symbols, fontsize=9, color="#e0e0e8")
    ax.set_xlabel("Hub Score (degree + betweenness)", fontsize=9, color="#787890", fontweight="600")
    ax.xaxis.set_major_locator(ticker.MaxNLocator(5))
    ax.tick_params(axis="x", colors="#787890", labelsize=8)
    ax.grid(axis="x", color="#1a1a24", linewidth=0.6, alpha=0.6, zorder=0)
    ax.set_axisbelow(True)

    for spine in ax.spines.values():
        spine.set_color("#252535")
        spine.set_linewidth(0.8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Legend
    legend_handles = [
        plt.Line2D([0], [0], color="#4ade80", linewidth=8, label="Has repurposing candidate"),
        plt.Line2D([0], [0], color="#818cf8", linewidth=8, label="No candidate yet"),
    ]
    legend = ax.legend(
        handles=legend_handles, loc="lower right", fontsize=7,
        framealpha=0.9, facecolor="#13131a", edgecolor="#252535", labelcolor="#787890",
    )

    ax.set_title("Lupus Gene Hub Scores", fontsize=12, fontweight="700", color="#e0e0e8", pad=10)
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="#0a0a0f")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def _run_ppi_communities(G: "nx.Graph") -> dict:
    """
    Detect communities using Louvain algorithm.

    Returns: {node_id: community_index}
    On failure (too few nodes), assigns all to community 0.
    """
    try:
        import networkx as nx
        communities = nx.community.louvain_communities(G, seed=42, weight="score")
        node_community = {}
        for idx, comm in enumerate(communities):
            for node_id in comm:
                node_community[node_id] = idx
        return node_community
    except Exception:
        return {n: 0 for n in G.nodes()}


# ── Community color palette (12 distinct dark-theme-friendly colors) ────

COMMUNITY_PALETTE = [
    "#4ade80",  # green
    "#818cf8",  # indigo
    "#f472b6",  # pink
    "#fbbf24",  # amber
    "#22d3ee",  # cyan
    "#c084fc",  # purple
    "#fb923c",  # orange
    "#38bdf8",  # sky
    "#a78bfa",  # violet
    "#fb7185",  # rose
    "#34d399",  # emerald
    "#e879f9",  # fuchsia
]


def _generate_ppi_network_plot(ppi_graph: dict, hub_scores: list) -> str:
    """
    Generate a network layout visualization of the PPI graph.

    Uses spring layout positioning via networkx.
    - Nodes colored by Louvain community (distinct palette)
    - Lupus seed genes have brighter fill and thicker border
    - Node size proportional to degree
    - Edge width by STRING score; top 10 edges labeled with scores
    - Labels for seed genes and high-degree non-seed nodes

    Returns base64-encoded PNG or empty string if no data / no matplotlib.
    """
    if not MPL_AVAILABLE or not ppi_graph:
        return ""

    nodes = ppi_graph.get("nodes", [])
    edges = ppi_graph.get("edges", [])
    if not nodes:
        return ""

    try:
        import networkx as nx
    except ImportError:
        return ""

    # ── Build networkx graph ─────────────────────────────────────────
    G = nx.Graph()
    node_ids = set()

    for n in nodes:
        nid = n.get("id", n.get("symbol", ""))
        node_ids.add(nid)
        is_seed = n.get("is_seed", False) or n.get("is_lupus_gene", False)
        G.add_node(nid, symbol=n.get("symbol", nid), is_seed=is_seed)

    edge_list = []  # preserve order for width/alpha lists
    for e in edges:
        src = e.get("source", "")
        tgt = e.get("target", "")
        if src in node_ids and tgt in node_ids:
            score = float(e.get("score", 0.5))
            G.add_edge(src, tgt, score=score)
            edge_list.append((src, tgt, score))

    if G.number_of_nodes() == 0:
        return ""

    # ── Community detection ──────────────────────────────────────────
    node_community = _run_ppi_communities(G)
    n_communities = len(set(node_community.values()))

    # ── Compute layout ───────────────────────────────────────────────
    pos = nx.spring_layout(G, k=2.0, iterations=50, seed=42, weight="score")

    # ── Build degree map for sizing ──────────────────────────────────
    max_deg = max(max(dict(G.degree()).values()), 1) if G.number_of_nodes() > 0 else 1

    # ── Plot ─────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(14, 10))
    fig.patch.set_facecolor("#0a0a0f")
    ax.set_facecolor("#0a0a0f")
    ax.axis("off")

    # Draw edges with weight-based alpha/width
    edge_widths = []
    edge_alphas = []
    for u, v, data in G.edges(data=True):
        score = data.get("score", 0.5)
        edge_widths.append(max(0.2, score * 2.5))
        edge_alphas.append(min(0.6, max(0.08, score * 0.5)))

    nx.draw_networkx_edges(
        G, pos, ax=ax,
        width=edge_widths,
        alpha=edge_alphas,
        edge_color="#a0a0c0",
        style="solid",
    )

    # ── Annotate top 10 strongest edges with scores ──────────────────
    if edge_list:
        top_edges = sorted(edge_list, key=lambda e: e[2], reverse=True)[:10]
        for src, tgt, score in top_edges:
            if src in pos and tgt in pos:
                mx = (pos[src][0] + pos[tgt][0]) / 2
                my = (pos[src][1] + pos[tgt][1]) / 2
                ax.text(
                    mx, my, f"{score:.2f}",
                    fontsize=4.5, color="#787890", alpha=0.7,
                    ha="center", va="center",
                    bbox=dict(boxstyle="round,pad=0.1", fc="#0a0a0f", ec="none", alpha=0.6),
                )

    # ── Separate seed vs non-seed nodes ──────────────────────────────
    seed_nodes = [n for n, d in G.nodes(data=True) if d.get("is_seed")]
    other_nodes = [n for n, d in G.nodes(data=True) if not d.get("is_seed")]

    def node_size(n):
        deg = G.degree(n)
        return 80 + (deg / max_deg) * 420

    # Draw non-seed nodes first (behind)
    if other_nodes:
        other_colors = [
            COMMUNITY_PALETTE[node_community.get(n, 0) % len(COMMUNITY_PALETTE)]
            for n in other_nodes
        ]
        nx.draw_networkx_nodes(
            G, pos, ax=ax,
            nodelist=other_nodes,
            node_size=[node_size(n) for n in other_nodes],
            node_color=other_colors,
            alpha=0.7,
            edgecolors="#1a1a24",
            linewidths=0.5,
        )

    # Draw seed nodes on top (brighter, thicker border)
    if seed_nodes:
        seed_colors = [
            COMMUNITY_PALETTE[node_community.get(n, 0) % len(COMMUNITY_PALETTE)]
            for n in seed_nodes
        ]
        nx.draw_networkx_nodes(
            G, pos, ax=ax,
            nodelist=seed_nodes,
            node_size=[node_size(n) for n in seed_nodes],
            node_color=seed_colors,
            alpha=0.9,
            edgecolors="#ffffff",
            linewidths=1.2,
        )

    # Labels: all seed nodes + high-degree non-seed nodes
    label_nodes = set(seed_nodes)
    deg_median = sorted(dict(G.degree()).values())[len(G.nodes()) // 2] if G.nodes() else 0
    for n in other_nodes:
        if G.degree(n) >= max(3, deg_median):
            label_nodes.add(n)

    labels = {n: G.nodes[n].get("symbol", n)[:12] for n in label_nodes}
    nx.draw_networkx_labels(
        G, pos, labels, ax=ax,
        font_size=7,
        font_color="#e0e0e8",
        font_weight="600",
    )

    # ── Legend ───────────────────────────────────────────────────────
    legend_handles = [
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#4ade80",
                   markersize=10, markeredgecolor="#ffffff", markeredgewidth=1.2,
                   label="Lupus Gene (seed)"),
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#818cf8",
                   markersize=8, markeredgecolor="#1a1a24", markeredgewidth=0.5,
                   label="Interacting Protein"),
        plt.Line2D([0], [0], color="#a0a0c0", linewidth=1.5, label="PPI (score)"),
    ]
    # Add community count
    if n_communities > 1:
        legend_handles.append(
            plt.Line2D([0], [0], marker="", linestyle="",
                       label=f"{n_communities} communities (Louvain)")
        )

    legend = ax.legend(
        handles=legend_handles, loc="upper left", fontsize=7,
        framealpha=0.9, facecolor="#13131a", edgecolor="#252535",
        labelcolor="#787890", borderpad=0.8,
    )

    ax.set_title(
        "PPI Network — Lupus Seed Genes & Interactors"
        + (f" ({n_communities} communities)" if n_communities > 1 else ""),
        fontsize=13, fontweight="700", color="#e0e0e8", pad=12,
    )

    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="#0a0a0f")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def _generate_ppi_interactive(ppi_graph: dict, hub_scores: list) -> str:
    """
    Generate an interactive PPI network using pyvis (HTML/JS).

    Features:
      - Zoom, pan, drag nodes
      - Hover tooltips with symbol, degree, community
      - Nodes colored by Louvain community
      - Edge width by STRING score
      - Saves standalone HTML to bioinformatics/data/ppi_interactive.html

    Returns the file path on success, or empty string on failure.
    """
    if not ppi_graph:
        return ""

    nodes = ppi_graph.get("nodes", [])
    edges = ppi_graph.get("edges", [])
    if not nodes:
        return ""

    try:
        import networkx as nx
        from pyvis.network import Network
    except ImportError:
        return ""

    # ── Build networkx graph ────────────────────────────────────────
    G = nx.Graph()
    node_ids = set()

    for n in nodes:
        nid = n.get("id", n.get("symbol", ""))
        node_ids.add(nid)
        is_seed = n.get("is_seed", False) or n.get("is_lupus_gene", False)
        G.add_node(nid, symbol=n.get("symbol", nid), is_seed=is_seed)

    for e in edges:
        src = e.get("source", "")
        tgt = e.get("target", "")
        if src in node_ids and tgt in node_ids:
            G.add_edge(src, tgt, score=float(e.get("score", 0.5)))

    if G.number_of_nodes() == 0:
        return ""

    # ── Community detection ─────────────────────────────────────────
    node_community = _run_ppi_communities(G)

    # ── Build degree map ────────────────────────────────────────────
    degrees = dict(G.degree())
    max_deg = max(degrees.values(), default=1)

    # ── Create pyvis network ─────────────────────────────────────────
    net = Network(
        height="700px", width="100%",
        bgcolor="#0a0a0f", font_color="#e0e0e8",
        directed=False, notebook=False,
    )

    # Physics for better layout
    net.set_options("""
    {
        "physics": {
            "barnesHut": {
                "gravitationalConstant": -2000,
                "centralGravity": 0.3,
                "springLength": 150,
                "springConstant": 0.04,
                "damping": 0.3
            },
            "minVelocity": 0.75
        },
        "edges": {
            "color": {"color": "#a0a0c0", "opacity": 0.4},
            "smooth": {"type": "continuous"}
        }
    }
    """)

    # Add nodes colored by community
    for nid, data in G.nodes(data=True):
        comm_idx = node_community.get(nid, 0) % len(COMMUNITY_PALETTE)
        color = COMMUNITY_PALETTE[comm_idx]
        is_seed = data.get("is_seed", False)
        symbol = data.get("symbol", nid)[:15]
        deg = degrees.get(nid, 0)
        size = 15 + (deg / max_deg) * 30
        border = 3 if is_seed else 1
        border_color = "#ffffff" if is_seed else "#1a1a24"

        title = (
            f"<b>{symbol}</b><br>"
            f"Degree: {deg}<br>"
            f"Community: {comm_idx + 1}<br>"
            f"Type: {'Seed Gene' if is_seed else 'Interactor'}"
        )

        net.add_node(
            nid,
            label=symbol,
            title=title,
            color=color,
            size=size,
            borderWidth=border,
            borderWidthSelected=border + 1,
            font={"color": "#e0e0e8", "size": 12 if is_seed else 10, "face": "Inter"},
        )

    # Add edges
    for src, tgt, data in G.edges(data=True):
        score = data.get("score", 0.5)
        width = max(0.5, score * 3)
        net.add_edge(
            src, tgt,
            value=score,
            width=width,
            title=f"STRING score: {score:.3f}",
        )

    # Save standalone HTML
    output_path = Path(__file__).parent / "data" / "ppi_interactive.html"
    os.makedirs(output_path.parent, exist_ok=True)
    net.save_graph(str(output_path))

    return str(output_path)


def _build_ppi_section(hub_scores: list, ppi_crossref: dict, ppi_graph: dict = None) -> str:
    """Build the PPI network analysis section."""
    if not hub_scores or not ppi_crossref:
        return ""

    # Top hubs table
    hub_rows = ""
    for i, h in enumerate(hub_scores[:15], 1):
        is_lupus = h.get("is_lupus_gene", False)
        row_class = "lupus" if is_lupus else "nonlupus"
        marker = "🧬" if is_lupus else "🔹"

        hub_rows += f"""
        <div class="hub-card {row_class}">
            <div class="hub-header">
                <span class="hub-symbol">{marker} {escape_html(h['symbol'])}</span>
                <span class="hub-score" style="color:{'#4ade80' if h['hub_score'] > 0.1 else '#fbbf24' if h['hub_score'] > 0.02 else '#787890'}">
                    {h['hub_score']:.4f}
                </span>
            </div>
            <div class="hub-meta">
                <span>Degree: {h.get('degree', 0)}</span>
                <span>Betweenness: {h.get('betweenness_centrality', 0):.4f}</span>
            </div>
            {f'<div class="hub-meta"><span>Gene: {escape_html(h.get("gene_id", ""))}</span></div>' if h.get("gene_id") else ''}
        </div>"""

    # Hub candidate matches
    matches_html = ""
    candidate_matches = ppi_crossref.get("hub_candidate_matches", [])
    if candidate_matches:
        for m in candidate_matches:
            cands = m.get("candidates", [])
            cand_str = ", ".join(
                f"{c['drug_name'][:35]} ({c.get('composite_score', '?')})"
                for c in cands[:3]
            )
            matches_html += f"""
            <div class="match-card">
                <span style="min-width:100px;font-weight:600;">🧬 {escape_html(m['symbol'])}</span>
                <span style="flex:1;font-size:0.82rem;">{cand_str}</span>
                <span class="badge badge-purple">{m.get('n_candidates', 0)} candidates</span>
            </div>"""

    # Untargeted hubs
    untargeted_html = ""
    untargeted = ppi_crossref.get("hub_untargeted", [])
    if untargeted:
        for u in untargeted:
            untargeted_html += f"""
            <div class="hub-card nonlupus">
                <div class="hub-header">
                    <span class="hub-symbol">💡 {escape_html(u['symbol'])}</span>
                    <span class="hub-score">Hub: {u['hub_score']:.4f}</span>
                </div>
                <div class="hub-meta">
                    <span>Degree: {u.get('degree', 0)}</span>
                    <span>New opportunity</span>
                </div>
            </div>"""

    # Generate PPI network graph (actual layout)
    network_plot_img = ""
    if ppi_graph:
        network_b64 = _generate_ppi_network_plot(ppi_graph, hub_scores)
        if network_b64:
            network_plot_img = f"""
        <div class="enrichment-plot">
            <img src="data:image/png;base64,{network_b64}"
                 alt="PPI Network Graph"
                 style="width:100%;max-width:1000px;border-radius:10px;"
                 loading="lazy">
            <p class="muted" style="margin-top:8px;font-size:0.72rem;">
                Spring layout. Nodes colored by Louvain community. Seed genes have white borders. Edge width ∝ STRING score.
            </p>
        </div>"""

    # Generate interactive PPI network (pyvis HTML)
    interactive_link = ""
    if ppi_graph:
        interactive_path = _generate_ppi_interactive(ppi_graph, hub_scores)
        if interactive_path:
            interactive_link = """
        <div class="enrichment-plot" style="padding:12px 20px;text-align:left;">
            <span style="font-weight:600;margin-right:12px;">🔍 Interactive Network:</span>
            <a href="data/ppi_interactive.html" target="_blank"
               style="color:#818cf8;font-size:0.85rem;text-decoration:underline;">
               Open interactive PPI network →
            </a>
            <span class="muted" style="margin-left:12px;font-size:0.72rem;">
               (zoom, pan, drag nodes, hover for details)
            </span>
        </div>"""

    # Generate PPI hub bar chart
    ppi_plot_img = ""
    ppi_plot_b64 = _generate_ppi_hub_chart(hub_scores, ppi_crossref)
    if ppi_plot_b64:
        ppi_plot_img = f"""
        <div class="enrichment-plot">
            <img src="data:image/png;base64,{ppi_plot_b64}"
                 alt="PPI Hub Score Chart"
                 style="width:100%;max-width:800px;border-radius:10px;"
                 loading="lazy">
        </div>"""

    return f"""
        <h2 class="section-title">🔗 PPI Network Hub Analysis</h2>
        <p class="muted" style="margin-bottom:12px;">
            Protein-protein interaction network via STRING. Hub scores combine degree and betweenness centrality.
        </p>
        {network_plot_img}
        {interactive_link}
        {ppi_plot_img}

        <h3 style="font-size:1rem;font-weight:600;margin:16px 0 10px;color:#a0a0b0;">🏆 Top Hub Proteins</h3>
        <div class="hub-grid">{hub_rows}</div>

        {f'<h3 style="font-size:1rem;font-weight:600;margin:24px 0 10px;color:#a0a0b0;">🎯 Hub Genes with Repurposing Candidates</h3>{matches_html}' if matches_html else ''}

        {f'<h3 style="font-size:1rem;font-weight:600;margin:24px 0 10px;color:#a0a0b0;">💡 Untargeted Hub Genes (New Opportunities)</h3><div class="hub-grid">{untargeted_html}</div>' if untargeted_html else ''}
    """


def _generate_gwas_manhattan(gwas_results: dict) -> str:
    """
    Generate a Manhattan-plot-style visualization of GWAS SNPs.

    X-axis: chromosomes ordered 1-22,X,Y with cumulative positions.
    Y-axis: -log10(p-value). Alternating chromosome colors.
    Horizontal line at genome-wide significance (p = 5e-8).

    Returns base64-encoded PNG or empty string if no data / no matplotlib.
    """
    if not MPL_AVAILABLE:
        return ""

    snp_data = gwas_results.get("snp_data", []) if gwas_results else []
    if not snp_data:
        return ""

    # ── Parse chromosome ordering ────────────────────────────────────
    chr_order = [str(i) for i in range(1, 23)] + ["X", "Y", "MT"]
    chr_rank = {c: i for i, c in enumerate(chr_order)}

    # Filter to valid chromosomes and sort
    valid_snps = []
    for s in snp_data:
        ch = s.get("chromosome", "")
        if ch in chr_rank and s.get("p_value", 1.0) > 0:
            valid_snps.append({
                "chromosome": ch,
                "position": int(s.get("position", 0)),
                "p_value": float(s["p_value"]),
                "neg_log_p": -math.log10(float(s["p_value"])),
                "rsid": s.get("rsid", ""),
            })

    if not valid_snps:
        return ""

    valid_snps.sort(key=lambda s: (chr_rank.get(s["chromosome"], 99), s["position"]))

    # Compute cumulative x positions for Manhattan layout
    chr_cumulative = {}
    chr_max_positions = {}  # track max position per chr for clean midpoint
    cum_pos = 0
    chr_midpoints = {}
    prev_chr = None
    x_positions = []

    for s in valid_snps:
        ch = s["chromosome"]
        if ch != prev_chr:
            if prev_chr is not None:
                # Midpoint = start offset + half of max position (no gap leaked)
                chr_midpoints[prev_chr] = chr_cumulative[prev_chr] + chr_max_positions[prev_chr] / 2
            if ch not in chr_cumulative:
                max_in_chr = max(s2["position"] for s2 in valid_snps if s2["chromosome"] == ch)
                chr_max_positions[ch] = max_in_chr
                chr_cumulative[ch] = cum_pos
                cum_pos += max_in_chr + 500000  # gap between chromosomes
            prev_chr = ch
        x = chr_cumulative[ch] + s["position"]
        x_positions.append(x)

    if prev_chr:
        chr_midpoints[prev_chr] = chr_cumulative[prev_chr] + chr_max_positions[prev_chr] / 2

    y_values = [s["neg_log_p"] for s in valid_snps]

    # ── Plot ─────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(14, 5))
    fig.patch.set_facecolor("#0a0a0f")
    ax.set_facecolor("#0a0a0f")

    # Alternating chromosome colors
    colors = []
    for s in valid_snps:
        ch_num = chr_rank.get(s["chromosome"], 0)
        colors.append("#818cf8" if ch_num % 2 == 0 else "#4ade80")

    ax.scatter(x_positions, y_values, c=colors, s=12, alpha=0.8, edgecolors="none", zorder=3)

    # Genome-wide significance line
    gw_sig = -math.log10(5e-8)
    ax.axhline(y=gw_sig, color="#f43f5e", linewidth=1, linestyle="--", alpha=0.6, zorder=1)
    ax.text(x_positions[-1] * 0.01, gw_sig + 0.3, "p = 5×10⁻⁸", fontsize=7, color="#f43f5e", alpha=0.7)

    # Suggestive line
    sugg = -math.log10(1e-5)
    ax.axhline(y=sugg, color="#fbbf24", linewidth=0.7, linestyle="--", alpha=0.4, zorder=1)

    # Chromosome labels
    ax.set_xticks([chr_midpoints[c] for c in sorted(chr_midpoints.keys(), key=lambda c: chr_rank.get(c, 99))])
    ax.set_xticklabels(
        [c for c in sorted(chr_midpoints.keys(), key=lambda c: chr_rank.get(c, 99))],
        fontsize=8, color="#787890",
    )

    ax.set_ylabel("-log₁₀(p-value)", fontsize=10, color="#787890", fontweight="600")
    ax.tick_params(axis="y", colors="#787890", labelsize=8)
    ax.yaxis.set_major_locator(ticker.MaxNLocator(6))
    ax.grid(axis="y", color="#1a1a24", linewidth=0.6, alpha=0.6, zorder=0)
    ax.set_axisbelow(True)
    ax.set_xlim(0, x_positions[-1] * 1.01 if x_positions else 1)

    for spine in ax.spines.values():
        spine.set_color("#252535")
        spine.set_linewidth(0.8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_visible(False)

    # ── Annotate top SNPs ───────────────────────────────────────────
    # Label top 5 most significant SNPs by -log10(p)
    top_n = min(5, len(valid_snps))
    top_indices = sorted(range(len(y_values)), key=lambda i: y_values[i], reverse=True)[:top_n]
    for idx in top_indices:
        rsid = valid_snps[idx]["rsid"]
        label = rsid if rsid else f"chr{valid_snps[idx]['chromosome']}:{valid_snps[idx]['position']}"
        ax.annotate(
            label,
            (x_positions[idx], y_values[idx]),
            textcoords="offset points",
            xytext=(0, 6),
            ha="center",
            fontsize=6,
            color="#e0e0e8",
            alpha=0.85,
            fontweight="600",
        )

    ax.set_title("GWAS Manhattan Plot — SLE/Lupus SNPs", fontsize=12, fontweight="700", color="#e0e0e8", pad=10)
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="#0a0a0f")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def _build_gwas_section(gwas_results: dict, gwas_crossref: dict) -> str:
    """Build the GWAS annotation section."""
    cards_html = ""

    # Validated genes
    validated = gwas_crossref.get("validated", {})
    for gene_name, info in sorted(
        validated.items(), key=lambda x: x[1]["n_gwas_studies"], reverse=True
    ):
        cards_html += f"""
        <div class="gwas-card validated">
            <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                <strong>{escape_html(gene_name)}</strong>
                <span class="badge badge-green">Validated</span>
            </div>
            <div class="muted" style="font-size:0.75rem;">
                {info['n_gwas_studies']} GWAS studies | KG OR={info.get('odds_ratio', 'N/A')}
            </div>
            <div class="muted" style="font-size:0.72rem;margin-top:4px;">{escape_html(info.get('category', ''))}</div>
        </div>"""

    # Novel genes (top 8)
    novel = gwas_crossref.get("novel", {})
    for gene_name, info in sorted(
        novel.items(), key=lambda x: x[1]["n_studies"], reverse=True
    )[:8]:
        cards_html += f"""
        <div class="gwas-card novel">
            <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                <strong>{escape_html(gene_name)}</strong>
                <span class="badge badge-yellow">Novel</span>
            </div>
            <div class="muted" style="font-size:0.75rem;">
                {info['n_studies']} GWAS studies | Best P={info['best_p_value']:.1e}
            </div>
        </div>"""

    # Missing genes
    missing = gwas_crossref.get("missing", {})
    for gene_id, info in missing.items():
        cards_html += f"""
        <div class="gwas-card missing">
            <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                <strong>{escape_html(info['name'][:40])}</strong>
                <span class="badge badge-red">No GWAS hit</span>
            </div>
            <div class="muted" style="font-size:0.75rem;">{escape_html(info.get('category', ''))}</div>
        </div>"""

    # Generate Manhattan plot
    manhattan_img = ""
    manhattan_b64 = _generate_gwas_manhattan(gwas_results)
    if manhattan_b64:
        snp_count = len(gwas_results.get("snp_data", [])) if gwas_results else 0
        manhattan_img = f"""
        <div class="enrichment-plot">
            <img src="data:image/png;base64,{manhattan_b64}"
                 alt="GWAS Manhattan Plot"
                 style="width:100%;max-width:1100px;border-radius:10px;"
                 loading="lazy">
            <p class="muted" style="margin-top:8px;font-size:0.72rem;">
                {snp_count} SNPs across chromosomes. Red dashed line = genome-wide significance (p=5×10⁻⁸). Yellow = suggestive (p=1×10⁻⁵).
            </p>
        </div>"""

    return f"""
        <h2 class="section-title">🧬 GWAS Catalog Annotation</h2>
        <p class="muted" style="margin-bottom:12px;">
            NHGRI-EBI GWAS Catalog results for SLE/lupus studies.
            Validated = found in both GWAS and KG. Novel = GWAS only. No GWAS hit = KG genes without GWAS evidence.
        </p>
        {manhattan_img}
        <div class="gwas-grid">{cards_html}</div>
    """


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
