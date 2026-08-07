"""Pure JSON and HTML dossier renderers."""

from __future__ import annotations

import html
import json
from pathlib import Path
from urllib.parse import urlsplit

from med_research.pipeline.reporting import provenance_footer_html

from .schemas import EvidenceDossier

DISCLAIMER = (
    "For research purposes only. This computational prioritization is not medical advice "
    "and requires experimental and clinical validation."
)


def dossier_to_json(dossier: EvidenceDossier, *, indent: int = 2) -> str:
    return json.dumps(
        dossier.model_dump(mode="json"), indent=indent, ensure_ascii=False, sort_keys=True
    )


def _provenance_html(dossier: EvidenceDossier) -> str:
    provenance = dict(dossier.manifest.get("provenance", {}) or {})
    if not provenance:
        return ""
    if "run_id" not in provenance and dossier.run_id:
        provenance["run_id"] = dossier.run_id
    return provenance_footer_html(provenance)


def _ranking_rows(rankings) -> str:
    rows = [
        "<table><tr><th>Candidate</th><th>Score</th><th>Confidence</th><th>Evidence quality</th><th>Explanation</th></tr>"
    ]
    for item in rankings:
        rows.append(
            "<tr>"
            f"<td>{html.escape(item.name)} <code>{html.escape(item.candidate_id)}</code></td>"
            f"<td>{item.score:.2f}</td>"
            f"<td>{html.escape(item.confidence_band)}</td>"
            f"<td>{item.component_scores.get('evidence_quality', 0):.2f}</td>"
            f"<td>{html.escape(item.explanation)}</td>"
            "</tr>"
        )
    rows.append("</table>")
    return "".join(rows)


def _safe_link(url: str, title: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return html.escape(title)
    return f'<a href="{html.escape(url, quote=True)}">{html.escape(title)}</a>'


def render_html(dossier: EvidenceDossier) -> str:
    evidence_rows = []
    for record in dossier.evidence:
        evidence_rows.append(
            "<tr>"
            f"<td>{html.escape(record.source)}</td>"
            f"<td>{html.escape(record.native_id or record.evidence_id)}</td>"
            f"<td>{_safe_link(record.url, record.title)}</td>"
            f"<td>{html.escape(record.snippet)}</td>"
            f"<td>{html.escape(record.quality_tier.replace('_', ' ').title())} ({record.quality_score:.2f})<br>{html.escape(record.quality_rationale)}</td>"
            "</tr>"
        )
    claim_rows = []
    for claim in dossier.claims:
        claim_rows.append(
            "<tr>"
            f"<td>{html.escape(claim.subject_name)}</td>"
            f"<td>{html.escape(claim.relationship)}</td>"
            f"<td>{html.escape(claim.text)}</td>"
            f"<td>{claim.confidence:.3f}</td>"
            f"<td>{html.escape(', '.join(claim.evidence_ids))}</td>"
            "</tr>"
        )
    graph_rows = []
    for explanation in dossier.graph_explanations:
        path = (
            " → ".join(explanation.path_labels) if explanation.path_labels else explanation.reason
        )
        graph_rows.append(
            "<tr>"
            f"<td>{html.escape(explanation.candidate_id)}</td>"
            f"<td>{html.escape(explanation.status)}</td>"
            f"<td>{html.escape(path)}</td>"
            "</tr>"
        )
    warning_html = (
        "".join(f"<li>{html.escape(warning)}</li>" for warning in dossier.warnings)
        or "<li>None</li>"
    )
    limitation_html = "".join(f"<li>{html.escape(item)}</li>" for item in dossier.limitations)
    return f"""<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>Evidence Dossier — {html.escape(dossier.request.question)}</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:1200px;margin:2rem auto;padding:0 1rem;color:#172033;line-height:1.5}}
h1{{margin-bottom:.25rem}} h2{{margin-top:2rem;border-bottom:2px solid #dbe4f0;padding-bottom:.35rem}}
.meta,.notice{{background:#f4f7fb;border:1px solid #dbe4f0;border-radius:8px;padding:1rem}}
.notice{{background:#fff8e6;border-color:#edc96b}} table{{width:100%;border-collapse:collapse;font-size:.92rem}}
th,td{{border:1px solid #dbe4f0;padding:.55rem;text-align:left;vertical-align:top}} th{{background:#edf3fa}}
code{{font-size:.8em;color:#52647a}} a{{color:#0b5cad}} @media print{{body{{margin:0}} .no-print{{display:none}}}}
</style></head><body>
<h1>Evidence-to-Hypothesis Workspace</h1>
<p><strong>Research question:</strong> {html.escape(dossier.request.question)}</p>
<div class=\"meta\"><strong>Run:</strong> {html.escape(dossier.run_id)}<br><strong>Disease:</strong> {html.escape(dossier.request.disease_id)}<br><strong>Sources:</strong> {html.escape(", ".join(dossier.request.sources))}<br><strong>Evidence records:</strong> {len(dossier.evidence)}<br><strong>Claims:</strong> {len(dossier.claims)}</div>
{_provenance_html(dossier)}
<div class=\"notice\"><strong>Research-only notice:</strong> {html.escape(DISCLAIMER)}</div>
<h2>Drug prioritization</h2>{_ranking_rows(dossier.drug_rankings)}
<h2>Target prioritization</h2>{_ranking_rows(dossier.target_rankings)}
<h2>Evidence and citations</h2><table><tr><th>Source</th><th>ID</th><th>Title</th><th>Snippet</th><th>Evidence quality</th></tr>{"".join(evidence_rows)}</table>
<h2>Quality methodology</h2><p>Quality tiers are transparent heuristics, not formal risk-of-bias assessments: Tier 1 prioritizes regulatory labels and randomized or late-phase trials; Tier 2 covers GWAS and observational evidence; Tier 3 covers other peer-reviewed evidence; Tier 4 flags non-peer-reviewed preprints. Inspect the cited study before drawing conclusions.</p>
<h2>Claims and confidence</h2><table><tr><th>Subject</th><th>Relationship</th><th>Claim</th><th>Confidence</th><th>Evidence IDs</th></tr>{"".join(claim_rows)}</table>
<h2>Knowledge-graph explanations</h2><table><tr><th>Candidate</th><th>Status</th><th>Path or reason</th></tr>{"".join(graph_rows)}</table>
<h2>Warnings and limitations</h2><ul>{warning_html}</ul><ul>{limitation_html}</ul>
<footer><p>{html.escape(DISCLAIMER)}</p></footer>
</body></html>"""


def write_json(dossier: EvidenceDossier, path: str | Path) -> Path:
    output = Path(path)
    output.write_text(dossier_to_json(dossier), encoding="utf-8")
    return output


def write_html(dossier: EvidenceDossier, path: str | Path) -> Path:
    output = Path(path)
    output.write_text(render_html(dossier), encoding="utf-8")
    return output
