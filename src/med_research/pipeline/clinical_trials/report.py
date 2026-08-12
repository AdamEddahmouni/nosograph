"""Disease-aware clinical trial tracker HTML report generator.

Generates a standalone HTML report showing:
  - Trial statistics and phase distribution chart
  - Mechanism of action breakdown
  - KG-cross-referenced trials table
  - Top genes and drugs in clinical development
"""

import base64
import io
from datetime import datetime
from pathlib import Path

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker

    MPL_AVAILABLE = True
except ImportError:
    MPL_AVAILABLE = False


PHASE_LABELS = {
    "EARLY_PHASE1": "Early Phase 1",
    "PHASE1": "Phase 1",
    "PHASE2": "Phase 2",
    "PHASE3": "Phase 3",
    "PHASE4": "Phase 4",
}

PHASE_COLORS = {
    "Early Phase 1": "#f472b6",
    "Phase 1": "#60a5fa",
    "Phase 2": "#fbbf24",
    "Phase 3": "#4ade80",
    "Phase 4": "#c084fc",
}

STATUS_COLORS = {
    "RECRUITING": "#4ade80",
    "ACTIVE_NOT_RECRUITING": "#60a5fa",
    "COMPLETED": "#c084fc",
    "NOT_YET_RECRUITING": "#fbbf24",
    "TERMINATED": "#f87171",
    "WITHDRAWN": "#f87171",
    "SUSPENDED": "#fbbf24",
    "UNKNOWN": "#787890",
}


def generate_ct_report(
    results: dict, disease_id: str = "sle", *, provenance: dict | None = None
) -> str:
    """Generate an HTML report from disease-specific trial results."""
    output_path = Path(__file__).parent / "ct_report.html"
    from med_research.pipeline.reporting import disease_context, render_report

    context = disease_context(disease_id)

    trials = results["trials"]
    stats = results["stats"]
    kg_crossref = results["kg_crossref"]

    # ── Phase chart ─────────────────────────────────────────────────
    phase_chart_b64 = _generate_phase_chart(stats["phases"]) if MPL_AVAILABLE else ""

    # ── MoA chart ────────────────────────────────────────────────────
    moa_chart_b64 = _generate_moa_chart(stats["moas"]) if MPL_AVAILABLE else ""

    # ── Stats cards ──────────────────────────────────────────────────
    stats_html = _build_stats_html(stats)

    # ── Trials table ─────────────────────────────────────────────────
    trials_table_html = _build_trials_table(trials)

    # ── Matched trials ───────────────────────────────────────────────
    matched_html = _build_matched_section(kg_crossref)

    # ── Top genes/drugs ──────────────────────────────────────────────
    genes_drugs_html = _build_genes_drugs_section(kg_crossref)

    # ── Assemble via template ──────────────────────────────────────
    html = render_report(
        "reports/clinical_trials.html",
        {
            "ctx_0": stats["total_trials"],
            "ctx_1": stats["kg_matched_trials"],
            "ctx_2": datetime.now().strftime("%B %d, %Y at %H:%M"),
            "ctx_3": stats_html,
            "ctx_4": (
                f'<div class="chart-card"><h4>Trials by Phase</h4><img src="data:image/png;base64,{phase_chart_b64}" alt="Phase Distribution Chart"/></div>'
                if phase_chart_b64
                else '<div class="chart-card"><p class="subtitle" style="padding:40px">📊 Install matplotlib for phase charts</p></div>'
            ),
            "ctx_5": (
                f'<div class="chart-card"><h4>Mechanism of Action Categories</h4><img src="data:image/png;base64,{moa_chart_b64}" alt="MoA Chart"/></div>'
                if moa_chart_b64
                else ""
            ),
            "ctx_6": matched_html,
            "ctx_7": genes_drugs_html,
            "ctx_8": trials_table_html,
            "ctx_disease": context["name"],
            "ctx_disease_id": context["id"],
        },
        disease_id,
        provenance=provenance,
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return str(output_path)


def _generate_phase_chart(phases: dict) -> str:
    """Generate a phase distribution bar chart as base64 PNG."""
    fig, ax = plt.subplots(figsize=(7, 4.5))
    fig.patch.set_facecolor("#13131a")
    ax.set_facecolor("#13131a")

    phase_order = ["Early Phase 1", "Phase 1", "Phase 2", "Phase 3", "Phase 4"]
    labels = [p for p in phase_order if p in phases]
    values = [phases.get(p, 0) for p in labels]
    colors = [PHASE_COLORS.get(p, "#60a5fa") for p in labels]

    bars = ax.bar(labels, values, color=colors, edgecolor="#252535", linewidth=0.5, width=0.6)
    for bar, val in zip(bars, values, strict=True):
        if val > 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 1,
                str(val),
                ha="center",
                va="bottom",
                fontsize=11,
                fontweight="bold",
                color="#e0e0e8",
            )

    ax.set_ylabel("Number of Trials", color="#787890", fontsize=9)
    ax.tick_params(colors="#787890", labelsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_color("#252535")
    ax.spines["left"].set_color("#252535")
    ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=120, facecolor="#13131a", bbox_inches="tight")
    plt.close()
    return base64.b64encode(buf.getvalue()).decode()


def _generate_moa_chart(moas: dict) -> str:
    """Generate a horizontal bar chart for mechanism of action categories."""
    fig, ax = plt.subplots(figsize=(7, 4.5))
    fig.patch.set_facecolor("#13131a")
    ax.set_facecolor("#13131a")

    sorted_moas = sorted(moas.items(), key=lambda x: x[1])
    labels = [m[0] for m in sorted_moas]
    values = [m[1] for m in sorted_moas]

    colors = [
        "#60a5fa",
        "#34d399",
        "#fbbf24",
        "#f472b6",
        "#c084fc",
        "#22d3ee",
        "#818cf8",
        "#f87171",
    ][: len(labels)]
    colors = colors[::-1] if len(colors) >= len(labels) else colors

    bars = ax.barh(
        labels, values, color=colors[: len(labels)], edgecolor="#252535", linewidth=0.5, height=0.6
    )
    for bar, val in zip(bars, values, strict=True):
        if val > 0:
            ax.text(
                bar.get_width() + 0.3,
                bar.get_y() + bar.get_height() / 2,
                str(val),
                ha="left",
                va="center",
                fontsize=10,
                fontweight="bold",
                color="#e0e0e8",
            )

    ax.set_xlabel("Number of Trials", color="#787890", fontsize=9)
    ax.tick_params(colors="#e0e0e8", labelsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_color("#252535")
    ax.spines["left"].set_color("#252535")
    ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=120, facecolor="#13131a", bbox_inches="tight")
    plt.close()
    return base64.b64encode(buf.getvalue()).decode()


def _build_stats_html(stats: dict) -> str:
    """Build the stats cards section."""
    cards = [
        ("📋", str(stats["total_trials"]), "Total Trials", "#60a5fa"),
        ("🔬", str(stats["kg_matched_trials"]), "KG-Matched Trials", "#34d399"),
        ("👥", f"{stats['total_enrollment']:,}", "Total Enrollment", "#fbbf24"),
        ("📊", str(stats.get("avg_enrollment", 0)), "Avg Enrollment", "#c084fc"),
        ("🏢", str(len(stats.get("top_sponsors", {}))), "Unique Sponsors", "#f472b6"),
        ("🧪", str(len(stats.get("moas", {}))), "MoA Categories", "#22d3ee"),
    ]
    return "".join(
        f'<div class="stat-card"><div class="stat-value" style="color:{color}">{val}</div>'
        f'<div class="stat-label">{label}</div></div>'
        for _, val, label, color in cards
    )


def _build_trials_table(trials: list) -> str:
    """Build the main trials data table."""
    rows = ""
    for t in trials[:50]:
        phases_html = (
            " ".join(
                f'<span class="phase-badge" style="background:rgba({_phase_rgba(t.get("phases", []))});'
                f'color:{_phase_color(t.get("phases", []))}">{PHASE_LABELS.get(p, p) if p in PHASE_LABELS else p}</span>'
                for p in t.get("phases", [])[:2]
            )
            or '<span class="phase-badge" style="color:#787890;background:rgba(120,120,144,0.1)">N/A</span>'
        )

        status = t.get("status", "")
        status_color = STATUS_COLORS.get(status, "#787890")

        interventions = ", ".join(t.get("interventions", [])[:3]) or "—"
        moa = t.get("moa_category", "")

        kg = t.get("kg_matches", {})
        kg_html = ""
        if kg.get("has_match"):
            kg_parts = []
            if kg.get("gene_count", 0) > 0:
                kg_parts.append(f"🧬 {kg['gene_count']}")
            if kg.get("drug_count", 0) > 0:
                kg_parts.append(f"💊 {kg['drug_count']}")
            kg_html = f'<span class="kg-badge" style="background:rgba(52,211,153,0.15);color:#34d399">{" ".join(kg_parts)}</span>'

        rows += f"""
        <tr>
            <td style="color:#60a5fa;font-size:0.75rem">{t["nct_id"]}</td>
            <td style="max-width:280px">{_escape_html(t.get("title", "")[:100])}</td>
            <td><span class="status-badge" style="background:rgba({_hex_to_rgba(status_color)});color:{status_color}">{status.replace("_", " ").title()}</span></td>
            <td>{phases_html}</td>
            <td style="max-width:200px;font-size:0.75rem">{_escape_html(interventions[:120])}</td>
            <td style="font-size:0.72rem"><span class="phase-badge" style="background:rgba(96,165,250,0.1);color:#60a5fa">{moa}</span></td>
            <td>{kg_html}</td>
        </tr>"""

    return f"""<table>
        <thead><tr>
            <th>NCT ID</th><th>Title</th><th>Status</th>
            <th>Phase</th><th>Interventions</th><th>MoA</th><th>KG Match</th>
        </tr></thead>
        <tbody>{rows}</tbody>
    </table>"""


def _build_matched_section(kg_crossref: dict) -> str:
    """Build the KG-matched trials section."""
    matched = kg_crossref.get("trials_with_matches", [])
    if not matched:
        return '<p class="subtitle" style="padding:20px;text-align:center">No trials matched KG entities.</p>'

    cards = ""
    for t in matched[:20]:
        genes = ", ".join(t.get("genes", [])[:4]) or "—"
        drugs = ", ".join(t.get("drugs", [])[:4]) or "—"

        cards += f"""
        <div class="match-card">
            <div class="match-header">
                <span class="match-title" style="color:#60a5fa">{t["nct_id"]}</span>
                <span class="status-badge" style="background:rgba({_hex_to_rgba(STATUS_COLORS.get(t.get("status", ""), "#787890"))});color:{STATUS_COLORS.get(t.get("status", ""), "#787890")}">{t.get("status", "").replace("_", " ").title()}</span>
            </div>
            <p style="font-size:0.82rem;margin-bottom:6px">{_escape_html(t.get("title", "")[:130])}</p>
            <div style="font-size:0.72rem;color:#787890;display:flex;gap:16px;flex-wrap:wrap">
                <span>Phase: {t.get("phase", "N/A")}</span>
                <span>🧬 Genes: {genes}</span>
                <span>💊 Drugs: {drugs}</span>
            </div>
        </div>"""

    return f'<p style="color:#787890;font-size:0.82rem;margin-bottom:12px">{len(matched)} trials matched KG entities</p>{cards}'


def _build_genes_drugs_section(kg_crossref: dict) -> str:
    """Build the top genes and drugs hit section."""
    gene_hits = kg_crossref.get("gene_hits", {})
    drug_hits = kg_crossref.get("drug_hits", {})

    max_gene = max(gene_hits.values()) if gene_hits else 1
    max_drug = max(drug_hits.values()) if drug_hits else 1

    gene_bars = ""
    for gene_id, count in list(gene_hits.items())[:12]:
        bar_width = int(count / max_gene * 150) if max_gene > 0 else 0
        gene_bars += f"""
        <div class="hit-bar">
            <span class="hit-label">{gene_id}</span>
            <div class="hit-fill" style="width:{bar_width}px;background:linear-gradient(90deg,#c084fc,#818cf8)"></div>
            <span class="hit-count">{count}</span>
        </div>"""

    drug_bars = ""
    for drug_id, count in list(drug_hits.items())[:12]:
        bar_width = int(count / max_drug * 150) if max_drug > 0 else 0
        drug_bars += f"""
        <div class="hit-bar">
            <span class="hit-label">{drug_id}</span>
            <div class="hit-fill" style="width:{bar_width}px;background:linear-gradient(90deg,#34d399,#60a5fa)"></div>
            <span class="hit-count">{count}</span>
        </div>"""

    return f"""
    <div class="gene-drug-grid">
        <div class="hit-card">
            <h4>🧬 Top Genes in Trials</h4>
            {gene_bars or '<p class="subtitle" style="font-size:0.78rem;padding:10px">No gene matches found</p>'}
        </div>
        <div class="hit-card">
            <h4>💊 Top Drugs in Trials</h4>
            {drug_bars or '<p class="subtitle" style="font-size:0.78rem;padding:10px">No drug matches found</p>'}
        </div>
    </div>"""


# ── Helpers ──────────────────────────────────────────────────────────


def _escape_html(text: str) -> str:
    if not text:
        return ""
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def _hex_to_rgba(hex_color: str) -> str:
    """Convert hex to comma-separated RGB for rgba()."""
    h = hex_color.lstrip("#")
    if len(h) == 6:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"{r},{g},{b},0.15"
    return "120,120,144,0.15"


def _phase_color(phases: list) -> str:
    """Get the best phase color."""
    for p in phases:
        if PHASE_LABELS.get(p, "") in PHASE_COLORS:
            return PHASE_COLORS[PHASE_LABELS[p]]
    return "#787890"


def _phase_rgba(phases: list) -> str:
    """Get rgba for phase color."""
    color = _phase_color(phases)
    return _hex_to_rgba(color)
