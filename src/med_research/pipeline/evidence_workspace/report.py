"""Pure JSON and HTML dossier renderers."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from med_research.pipeline.reporting import render_report

from .schemas import EvidenceDossier

DISCLAIMER = (
    "For research purposes only. This computational prioritization is not medical advice "
    "and requires experimental and clinical validation."
)


def dossier_to_json(dossier: EvidenceDossier, *, indent: int = 2) -> str:
    return json.dumps(
        dossier.model_dump(mode="json"), indent=indent, ensure_ascii=False, sort_keys=True
    )


def _ranking_rows(rankings: list[Any]) -> str:
    rows = [
        "<table><tr><th>Candidate</th><th>Score</th><th>Confidence</th>"
        "<th>Evidence quality</th><th>Explanation</th></tr>"
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


def _list_items(items: list[str], *, empty: str = "None") -> str:
    if not items:
        return f"<li>{html.escape(empty)}</li>"
    return "".join(f"<li>{html.escape(item)}</li>" for item in items)


def render_html(dossier: EvidenceDossier) -> str:
    evidence_rows = []
    for record in dossier.evidence:
        evidence_rows.append(
            "<tr>"
            f"<td>{html.escape(record.source)}</td>"
            f"<td>{html.escape(record.native_id or record.evidence_id)}</td>"
            f"<td>{_safe_link(record.url, record.title)}</td>"
            f"<td>{html.escape(record.snippet)}</td>"
            f"<td>{html.escape(record.quality_tier.replace('_', ' ').title())} "
            f"({record.quality_score:.2f})<br>{html.escape(record.quality_rationale)}</td>"
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
            " → ".join(explanation.path_labels)
            if explanation.path_labels
            else explanation.reason
        )
        graph_rows.append(
            "<tr>"
            f"<td>{html.escape(explanation.candidate_id)}</td>"
            f"<td>{html.escape(explanation.status)}</td>"
            f"<td>{html.escape(path)}</td>"
            "</tr>"
        )

    provenance = dict(dossier.manifest.get("provenance", {}) or {})
    if "run_id" not in provenance and dossier.run_id:
        provenance["run_id"] = dossier.run_id

    return render_report(
        "reports/evidence_workspace.html",
        {
            "question": dossier.request.question,
            "run_id": dossier.run_id,
            "disease_id": dossier.request.disease_id,
            "sources": ", ".join(dossier.request.sources),
            "evidence_count": len(dossier.evidence),
            "claim_count": len(dossier.claims),
            "disclaimer": DISCLAIMER,
            "drug_ranking_rows": _ranking_rows(dossier.drug_rankings),
            "target_ranking_rows": _ranking_rows(dossier.target_rankings),
            "evidence_rows": "".join(evidence_rows),
            "claim_rows": "".join(claim_rows),
            "graph_rows": "".join(graph_rows),
            "warning_items": _list_items(dossier.warnings),
            "limitation_items": _list_items(dossier.limitations, empty=""),
        },
        disease_id=dossier.request.disease_id,
        provenance=provenance,
    )


def write_json(dossier: EvidenceDossier, path: str | Path) -> Path:
    output = Path(path)
    output.write_text(dossier_to_json(dossier), encoding="utf-8")
    return output


def write_html(dossier: EvidenceDossier, path: str | Path) -> Path:
    output = Path(path)
    output.write_text(render_html(dossier), encoding="utf-8")
    return output
