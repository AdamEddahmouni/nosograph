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


def generate_literature_report(results: dict, entities: dict, candidates: list) -> str:
    """Generate an HTML report from literature mining results."""

    output_path = Path(__file__).parent / "literature_report.html"
    stats = results["stats"]
    candidate_support = results["candidate_support"]
    gene_coverage = results["gene_coverage"]
    drug_coverage = results["drug_coverage"]
    novel_entities = results.get("novel_entities", {})
    spacy_status = stats.get("spacy_ner", "not available")
    novel_count = stats.get("novel_entities_found", 0)
    extraction_stats = results.get("extraction_stats")

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

    # ── Assemble HTML ───────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Lupus Literature Mining Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            background: #0a0a0f; color: #e0e0e8; line-height: 1.6;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 24px; }}

        .hero {{
            background: linear-gradient(135deg, #0f1729, #1a1025, #0f1729);
            border: 1px solid #252535; border-radius: 16px;
            padding: 40px; margin-bottom: 32px; text-align: center;
        }}
        .hero h1 {{
            font-size: 2rem; font-weight: 800;
            background: linear-gradient(135deg, #818cf8, #c084fc, #f472b6);
            -webkit-background-clip: text; background-clip: text;
            -webkit-text-fill-color: transparent; margin-bottom: 8px;
        }}
        .hero .subtitle {{ color: #787890; font-size: 0.95rem; }}

        .stats-grid {{
            display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 14px; margin-bottom: 32px;
        }}
        .stat-card {{
            background: #13131a; border: 1px solid #252535;
            border-radius: 12px; padding: 20px; text-align: center;
        }}
        .stat-card .stat-value {{ font-size: 1.8rem; font-weight: 800; }}
        .stat-card .stat-label {{ color: #787890; font-size: 0.78rem; margin-top: 4px; }}

        .section-title {{
            font-size: 1.2rem; font-weight: 700; margin: 32px 0 14px;
            padding-bottom: 8px; border-bottom: 1px solid #252535;
        }}

        /* Tables */
        .table-container {{
            overflow-x: auto; background: #13131a;
            border: 1px solid #252535; border-radius: 12px; margin-bottom: 28px;
        }}
        table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
        th {{
            text-align: left; padding: 12px 14px; background: #1a1a24;
            color: #787890; font-weight: 600; font-size: 0.72rem;
            text-transform: uppercase; letter-spacing: 0.04em;
            border-bottom: 1px solid #252535;
        }}
        td {{ padding: 10px 14px; border-bottom: 1px solid #1a1a24; }}
        tr:hover td {{ background: rgba(129,140,248,0.03); }}
        .muted {{ color: #787890; font-size: 0.78rem; }}

        /* Bars */
        .bar-container {{
            display: flex; align-items: center; gap: 8px; min-width: 120px;
        }}
        .bar-fill {{
            height: 8px; background: linear-gradient(90deg, #4ade80, #22c55e);
            border-radius: 4px; min-width: 4px; transition: width 0.3s;
        }}
        .bar-label {{ font-size: 0.78rem; font-weight: 600; color: #a0a0b0; }}

        /* Article cards */
        .article-card {{
            background: #13131a; border: 1px solid #252535;
            border-radius: 10px; padding: 18px; margin-bottom: 12px;
            transition: border-color 0.2s;
        }}
        .article-card:hover {{ border-color: #4b5563; }}
        .article-header {{
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 6px;
        }}
        .article-score {{
            background: #818cf8; color: #fff; font-weight: 700;
            padding: 2px 10px; border-radius: 12px; font-size: 0.75rem;
        }}
        .article-pmid {{ color: #787890; font-size: 0.72rem; }}
        .article-pmid a {{ color: #818cf8; text-decoration: none; }}
        .article-card h4 {{ font-size: 0.9rem; margin-bottom: 8px; color: #e0e0e8; }}
        .article-abstract {{ font-size: 0.78rem; color: #787890; margin-bottom: 10px; }}
        .article-entities {{ display: flex; gap: 8px; flex-wrap: wrap; }}
        .entity-tag {{
            padding: 2px 8px; border-radius: 10px; font-size: 0.7rem;
            font-weight: 500;
        }}
        .entity-tag.gene {{ background: rgba(192,132,252,0.15); color: #c084fc; }}
        .entity-tag.drug {{ background: rgba(74,222,128,0.15); color: #4ade80; }}
        .entity-tag.novel {{ background: rgba(52,211,153,0.15); color: #34d399; }}

        /* Novel entities section */
        .novel-category {{ margin-bottom: 20px; }}
        .novel-category h4 {{
            font-size: 0.85rem; color: #a0a0b0; margin-bottom: 10px;
            font-weight: 600;
        }}
        .novel-tags {{ display: flex; flex-wrap: wrap; gap: 6px; }}

        .pmids {{ font-size: 0.75rem; }}
        .pmid-link {{
            color: #818cf8; text-decoration: none; margin-right: 6px;
            font-size: 0.72rem;
        }}

        footer {{
            text-align: center; padding: 40px; color: #787890; font-size: 0.75rem;
        }}
        footer a {{ color: #818cf8; }}

        @media (max-width: 768px) {{
            .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
            .hero {{ padding: 24px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="hero">
            <h1>📚 Lupus Literature Mining Report</h1>
            <p class="subtitle">
                PubMed Analysis of {stats['total_articles']} Articles · 
                Cross-Referenced Against {len(entities['genes'])} Genes & {len(entities['drugs'])} Drugs
            </p>
            <p class="subtitle" style="font-size:0.78rem;margin-top:8px;">
                Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')}
            </p>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value" style="color:#818cf8">{stats['total_articles']}</div>
                <div class="stat-label">Articles Analyzed</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color:#4ade80">{stats['articles_with_matches']}</div>
                <div class="stat-label">With KG Matches</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color:#c084fc">{stats['genes_found']}</div>
                <div class="stat-label">Unique Genes Found</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color:#fbbf24">{stats['drugs_found']}</div>
                <div class="stat-label">Unique Drugs Found</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color:#f472b6">{stats['candidates_supported']}</div>
                <div class="stat-label">Candidates with Lit Support</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color:#34d399">{novel_count}</div>
                <div class="stat-label">Novel Entities (spaCy)</div>
            </div>
{extraction_stat_card}
        </div>

{extraction_section}
        <h2 class="section-title">📋 Candidates with Literature Support</h2>
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>Drug</th><th>Target Gene</th><th>Score</th>
                        <th>Articles</th><th>PubMed Links</th>
                    </tr>
                </thead>
                <tbody>{candidate_rows}</tbody>
            </table>
        </div>

        <h2 class="section-title">🧬 Gene Literature Coverage</h2>
        <div class="table-container">
            <table>
                <thead>
                    <tr><th>Gene</th><th>Category</th><th>Articles</th></tr>
                </thead>
                <tbody>{gene_rows}</tbody>
            </table>
        </div>

        <h2 class="section-title">📄 Top Articles by KG Relevance</h2>
        {article_rows}

        <h2 class="section-title">🔬 Novel Entities Discovered (spaCy NER: {spacy_status})</h2>
        {novel_section}

        <footer>
            <p>Lupus Literature Mining Engine · PubMed search via BioPython Entrez</p>
            <p>Entity matching against the <a href="../knowledge_graph/web/index.html">Lupus Knowledge Graph</a></p>
            <p style="margin-top:8px;color:#6b7280;">
                Disclaimer: This is a computational research tool. Literature matches require manual verification.
            </p>
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
