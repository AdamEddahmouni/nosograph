"""Citation-ready exports for Evidence Workspace candidate reviews."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from typing import Any


def _markdown(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _candidate_reviews(run: dict[str, Any], reviews: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    return {(item["candidate_type"], item["candidate_id"]): item for item in reviews}


def _review_markdown(run: dict[str, Any], reviews: list[dict[str, Any]]) -> str:
    dossier = run.get("dossier") or {}
    request = dossier.get("request") or run.get("request") or {}
    provenance = (dossier.get("manifest") or {}).get("provenance") or {}
    review_by_candidate = _candidate_reviews(run, reviews)
    researcher_ids = sorted({item.get("researcher_id", "anonymous") for item in reviews})
    lines = [
        "# Evidence Workspace Review",
        "",
        f"- **Run:** `{_markdown(run.get('run_id'))}`",
        f"- **Disease:** `{_markdown(request.get('disease_id'))}`",
        f"- **Question:** {_markdown(request.get('question'))}",
        f"- **Sources:** {_markdown(', '.join(request.get('sources') or []))}",
        f"- **Completed:** {_markdown(dossier.get('completed_at') or run.get('updated_at'))}",
        f"- **Provenance fingerprint:** `{_markdown(provenance.get('fingerprint'))}`",
        f"- **Researcher:** {_markdown(', '.join(researcher_ids) or 'anonymous')}",
        "",
        "> Research use only. Computational prioritization is not medical advice or evidence of efficacy.",
        "",
    ]
    for heading, key, candidate_type in (
        ("Drug candidates", "drug_rankings", "drug"),
        ("Target candidates", "target_rankings", "target"),
    ):
        lines.extend([f"## {heading}", ""])
        rankings = dossier.get(key, [])
        if not rankings:
            lines.extend(["No candidates were ranked.", ""])
            continue
        for candidate in rankings:
            review = review_by_candidate.get((candidate_type, candidate.get("candidate_id", "")))
            lines.extend(
                [
                    f"### {_markdown(candidate.get('name'))} (`{_markdown(candidate.get('candidate_id'))}`)",
                    f"- **Score:** {_markdown(candidate.get('score'))} ({_markdown(candidate.get('confidence_band'))} confidence)",
                    f"- **Decision:** {_markdown((review or {}).get('decision', 'unreviewed'))}",
                    f"- **Rationale:** {_markdown((review or {}).get('rationale')) or 'Not recorded.'}",
                    f"- **Tags:** {_markdown(', '.join((review or {}).get('tags') or [])) or 'None'}",
                    f"- **Notes:** {_markdown((review or {}).get('notes')) or 'None'}",
                    f"- **What changed my mind:** {_markdown((review or {}).get('changed_my_mind')) or 'Not recorded.'}",
                    f"- **Model explanation:** {_markdown(candidate.get('explanation'))}",
                    f"- **Supporting claims:** {_markdown(', '.join(candidate.get('supporting_claim_ids') or [])) or 'None'}",
                    f"- **Contradicting claims:** {_markdown(', '.join(candidate.get('contradicting_claim_ids') or [])) or 'None'}",
                    "",
                ]
            )
    lines.extend(["## Evidence changes and limitations", ""])
    warnings = dossier.get("warnings") or []
    limitations = dossier.get("limitations") or []
    if warnings or limitations:
        for item in [*warnings, *limitations]:
            lines.append(f"- {_markdown(item)}")
    else:
        lines.append("No warnings or limitations were recorded.")
    lines.append("")
    lines.extend(
        [
            "## Citation key",
            "",
            "See `citations.csv` for source-native IDs, dates, URLs, and snippets. The original `dossier.json` is included unchanged for machine-readable provenance.",
            "",
        ]
    )
    return "\n".join(lines)


def _citations_csv(dossier: dict[str, Any]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["citation_key", "source", "native_id", "doi", "title", "published_date", "url", "snippet"],
        lineterminator="\n",
    )
    writer.writeheader()
    seen: set[str] = set()
    for index, evidence in enumerate(dossier.get("evidence", []), start=1):
        citation_key = evidence.get("native_id") or evidence.get("doi") or evidence.get("evidence_id") or f"evidence-{index}"
        if citation_key in seen:
            continue
        seen.add(citation_key)
        writer.writerow(
            {
                "citation_key": citation_key,
                "source": evidence.get("source", ""),
                "native_id": evidence.get("native_id", ""),
                "doi": evidence.get("doi", "") or "",
                "title": evidence.get("title", ""),
                "published_date": evidence.get("published_date", "") or "",
                "url": evidence.get("url", ""),
                "snippet": _markdown(evidence.get("snippet")),
            }
        )
    return output.getvalue()


def build_review_bundle(
    run: dict[str, Any],
    reviews: list[dict[str, Any]],
    review_events: list[dict[str, Any]] | None = None,
) -> io.BytesIO:
    """Build an in-memory ZIP containing review notes and exact source artifacts."""
    dossier = run.get("dossier") or {}
    provenance = (dossier.get("manifest") or {}).get("provenance") or {}
    payloads = {
        "review.md": _review_markdown(run, reviews),
        "citations.csv": _citations_csv(dossier),
        "dossier.json": json.dumps(dossier, indent=2, ensure_ascii=False, sort_keys=True),
        "reviews.json": json.dumps(reviews, indent=2, ensure_ascii=False, sort_keys=True),
        "review-events.json": json.dumps(review_events or [], indent=2, ensure_ascii=False, sort_keys=True),
        "provenance.json": json.dumps(provenance, indent=2, ensure_ascii=False, sort_keys=True),
    }
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for filename, content in payloads.items():
            bundle.writestr(filename, content)
    archive.seek(0)
    return archive
