"""
Lupus Literature Mining Report Generator

Generates a standalone HTML report showing:
  - Literature coverage statistics
  - Candidates with most literature support
  - Gene-level literature coverage with visual bars
  - Top articles ranked by knowledge graph relevance
"""

from datetime import datetime
from pathlib import Path

from med_research.pipeline.reporting import (
    apply_disease_labels,
    disease_context,
    provenance_footer_html,
)
from med_research.templates import env as template_env


def generate_literature_report(
    results: dict,
    entities: dict,
    candidates: list,
    disease_id: str = "sle",
    *,
    provenance: dict | None = None,
) -> str:
    """Generate an HTML report from disease-specific literature results."""

    output_path = Path(__file__).parent / "literature_report.html"
    context = disease_context(disease_id)
    stats = results["stats"]
    candidate_support = results["candidate_support"]
    gene_coverage = results["gene_coverage"]
    novel_entities = results.get("novel_entities", {})
    spacy_status = stats.get("spacy_ner", "not available")
    novel_count = stats.get("novel_entities_found", 0)
    extraction_stats = results.get("extraction_stats")
    variant_entities = results.get("variant_entities", [])
    clinical_entities = results.get("clinical_entities", [])
    dosage_entities = results.get("dosage_entities", [])
    variant_count = stats.get("variant_mentions", len(variant_entities))
    clinical_count = stats.get("clinical_mentions", len(clinical_entities))
    dosage_count = stats.get("dosage_mentions", len(dosage_entities))

    # ── Content extraction stat card ──────────────────────────────────
    extraction_stat_card = ""
    extraction_section = ""
    if extraction_stats:
        token_saved = extraction_stats.get("total_tokens", 0) - extraction_stats.get("kept_tokens", 0)
        token_pct = round(token_saved / max(extraction_stats.get("total_tokens", 1), 1) * 100)
        sent_kept = extraction_stats.get("kept_sentences", 0)
        sent_total = extraction_stats.get("total_sentences", 0)
        sent_pct = round(sent_kept / max(sent_total, 1) * 100)

        extraction_stat_card = f"""
            <div class="stat-card">
                <div class="stat-value" style="color:#f97316">{token_pct}%</div>
                <div class="stat-label">Tokens Filtered</div>
            </div>"""

        extraction_section = f"""
        <h2 class="section-title">✂️ AI Content Extraction</h2>
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value" style="color:#818cf8">{extraction_stats.get("abstracts_processed", 0)}</div>
                <div class="stat-label">Abstracts Filtered</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color:#4ade80">{sent_total}</div>
                <div class="stat-label">Total Sentences</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color:#c084fc">{sent_kept} ({sent_pct}%)</div>
                <div class="stat-label">Relevant Sentences Kept</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color:#fbbf24">{extraction_stats.get("total_tokens", 0):,}</div>
                <div class="stat-label">Total Tokens</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color:#f97316">{token_saved:,}</div>
                <div class="stat-label">Tokens Filtered Out</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color:#f472b6">{extraction_stats.get("fully_filtered", 0)}</div>
                <div class="stat-label">Fallbacks (no matches)</div>
            </div>
        </div>
        <p class="muted" style="text-align:center;margin:0 0 20px;">
            Content extraction filters abstracts to only sentences containing known KG entities
            (genes, drugs, pathways). This reduces NER processing tokens by ~{token_pct}% while
            preserving all literature evidence relevant to drug repurposing.
        </p>"""

    # Build gene name lookup
    gene_names = {gid: info.get("name", gid) for gid, info in entities["genes"].items()}

    # ── Candidate support rows ──────────────────────────────────────────
    candidate_rows = ""
    sorted_candidates = sorted(
        candidate_support.items(), key=lambda x: len(x[1]), reverse=True
    )
    for cid, articles in sorted_candidates:
        cand = next((c for c in candidates if c["id"] == cid), None)
        if not cand:
            continue
        article_count = len(articles)
        bar_width = min(article_count * 15, 150)

        articles_html = ""
        for a in articles[:5]:
            articles_html += (
                f'<a class="pmid-link" '
                f'href="https://pubmed.ncbi.nlm.nih.gov/{a["pmid"]}" '
                f'target="_blank" title="{escape_html(a["title"])}">'
                f'PMID:{a["pmid"]} ({a["year"]})</a> '
            )

        gene_name = gene_names.get(cand.get("gene_id", ""), cand.get("gene_id", "?"))
        score = cand.get("composite_score", 0)
        score_color = (
            "#4ade80" if score >= 8 else "#fbbf24" if score >= 7 else "#f87171"
        )

        candidate_rows += f"""
        <tr>
            <td><strong>{escape_html(cand['drug_name'][:60])}</strong></td>
            <td>{gene_name}</td>
            <td><span style="color:{score_color};font-weight:700">{score:.1f}</span></td>
            <td>
                <div class="bar-container">
                    <div class="bar-fill" style="width:{bar_width}px"></div>
                    <span class="bar-label">{article_count}</span>
                </div>
            </td>
            <td class="pmids">{articles_html}</td>
        </tr>"""

    # ── Gene coverage rows ──────────────────────────────────────────────
    gene_rows = ""
    sorted_genes = sorted(
        gene_coverage.items(), key=lambda x: x[1]["articles"], reverse=True
    )
    for gid, info in sorted_genes:
        gene_info = entities["genes"].get(gid, {"name": gid, "category": ""})
        bar_width = min(info["articles"] * 12, 120)

        gene_rows += f"""
        <tr>
            <td><strong>{escape_html(gene_info['name'][:50])}</strong></td>
            <td><span class="muted">{gene_info.get('category', '')}</span></td>
            <td>
                <div class="bar-container">
                    <div class="bar-fill" style="width:{bar_width}px;background:linear-gradient(90deg,#818cf8,#c084fc)"></div>
                    <span class="bar-label">{info['articles']}</span>
                </div>
            </td>
        </tr>"""

    # ── Top articles ────────────────────────────────────────────────────
    article_rows = ""
    top_articles = [
        a for a in results["article_matches"] if a["relevance_score"] > 0
    ][:20]
    for a in top_articles:
        kg = a["kg_matches"]
        gene_names_list = ", ".join(
            g["name"][:25] for g in list(kg["genes_found"].values())[:4]
        )
        drug_names_list = ", ".join(
            d["name"][:30] for d in list(kg["drugs_found"].values())[:4]
        )

        article_rows += f"""
        <div class="article-card">
            <div class="article-header">
                <span class="article-score">{a['relevance_score']}</span>
                <span class="article-pmid">
                    <a href="https://pubmed.ncbi.nlm.nih.gov/{a['pmid']}" target="_blank">
                        PMID:{a['pmid']}
                    </a>
                    · {a.get('year', 'N/A')} · {escape_html(a.get('journal', '')[:40])}
                </span>
            </div>
            <h4>{escape_html(a['title'])}</h4>
            <p class="article-abstract">{escape_html(a.get('abstract', '')[:400])}...</p>
            <div class="article-entities">
                {f'<span class="entity-tag gene">🧬 {gene_names_list}</span>' if gene_names_list else ''}
                {f'<span class="entity-tag drug">💊 {drug_names_list}</span>' if drug_names_list else ''}
            </div>
        </div>"""

    # ── Novel entities section ────────────────────────────────────────
    novel_section = ""
    if novel_entities:
        for category, entities_list in novel_entities.items():
            tags = "".join(
                f'<span class="entity-tag novel">{escape_html(e[:40])}</span>'
                for e in entities_list[:30]
            )
            icon = {"chemicals": "⚗️", "diseases": "🦠", "genes": "🧬"}.get(category, "🔬")
            novel_section += f"""
            <div class="novel-category">
                <h4>{icon} {category.title()} ({len(entities_list)} found)</h4>
                <div class="novel-tags">{tags}</div>
            </div>"""
        if not novel_section:
            novel_section = (
                '<p class="muted" style="padding:20px;text-align:center;">'
                'No novel entities found beyond the knowledge graph dictionary. '
                'Install spaCy + scispacy to enable biomedical NER.</p>'
            )
    else:
        novel_section = (
            '<p class="muted" style="padding:20px;text-align:center;">'
            'spaCy biomedical NER is not active. '
            'Install <code>spacy</code> + <code>scispacy</code> to discover '
            'novel drugs, genes, and diseases from the literature.</p>'
        )

    # ── Additional entity type sections ────────────────────────────────
    variant_section = ""
    if variant_entities:
        tags = "".join(
            f'<span class="entity-tag variant">{escape_html(v[:50])}</span>'
            for v in variant_entities[:30]
        )
        variant_section = f"""
        <h2 class="section-title">🧬 Genetic Variants & Mutations ({variant_count} mentions)</h2>
        <div class="novel-tags">{tags}</div>
        <br>"""

    clinical_section = ""
    if clinical_entities:
        tags = "".join(
            f'<span class="entity-tag clinical">{escape_html(c[:50])}</span>'
            for c in clinical_entities[:25]
        )
        clinical_section = f"""
        <h2 class="section-title">🏥 Clinical Trial Outcomes ({clinical_count} mentions)</h2>
        <div class="novel-tags">{tags}</div>
        <br>"""


    statistics_entities = results.get("statistics_entities", [])
    statistics_count = stats.get("statistics_mentions", len(statistics_entities))
    statistics_section = ""
    if statistics_entities:
        tags = "".join(
            f'<span class="entity-tag stats">{escape_html(item[:50])}</span>'
            for item in statistics_entities[:25]
        )
        statistics_section = f"""
        <h2 class="section-title">📊 Statistical Measures ({statistics_count} mentions)</h2>
        <div class="novel-tags">{tags}</div>
        <br>"""

    dosage_section = ""
    if dosage_entities:
        tags = "".join(
            f'<span class="entity-tag dosage">{escape_html(d[:50])}</span>'
            for d in dosage_entities[:25]
        )
        dosage_section = f"""
        <h2 class="section-title">💉 Dosage & Administration ({dosage_count} mentions)</h2>
        <div class="novel-tags">{tags}</div>
        <br>"""

    # ── Assemble HTML ───────────────────────────────────────────────────
    html = template_env.get_template("reports/literature_mining.html").render(
        ctx_0=stats['total_articles'],
        ctx_1=len(entities['genes']),
        ctx_2=len(entities['drugs']),
        ctx_3=datetime.now().strftime('%B %d, %Y at %H:%M'),
        ctx_4=stats['articles_with_matches'],
        ctx_5=stats['genes_found'],
        ctx_6=stats['drugs_found'],
        ctx_7=stats['candidates_supported'],
        ctx_8=novel_count,
        ctx_9=variant_count,
        ctx_10=clinical_count,
        ctx_11=dosage_count,
        ctx_12=extraction_stat_card,
        ctx_13=extraction_section,
        ctx_14=candidate_rows,
        ctx_15=gene_rows,
        ctx_16=article_rows,
        ctx_17=spacy_status,
        ctx_18=novel_section,
        ctx_19=variant_section,
        ctx_20=clinical_section,
        ctx_21=dosage_section,
        ctx_22=statistics_section,
        disease_id=context["name"],
        disease_id_raw=context["id"],
    )
    html = apply_disease_labels(html, disease_id)
    footer = provenance_footer_html(provenance)
    if footer:
        html = html.replace("</body>", f"{footer}\n</body>", 1)

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
