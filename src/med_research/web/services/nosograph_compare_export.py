"""Deterministic export rendering for persisted NosoGraph comparisons."""

from __future__ import annotations

from med_research.biomed.identifiers import canonical_json
from med_research.web.models.universal import (
    DimensionComparisonView,
    EntityStateRowView,
    NosoGraphCompareV2ResultView,
)

_DIMENSION_TITLES = {
    "phenotype": "Phenotype",
    "gene": "Gene",
    "pathway": "Pathway",
    "treatment": "Treatment",
    "evidence_coverage": "Evidence coverage",
}


def render_json(result: NosoGraphCompareV2ResultView) -> bytes:
    """Return the exact API wire payload as canonical UTF-8 JSON with one final LF."""
    payload = result.model_dump(mode="json")
    return (canonical_json(payload) + "\n").encode("utf-8")


def render_markdown(result: NosoGraphCompareV2ResultView) -> bytes:
    """Render a timestamp-free, byte-stable research report."""
    lines = [
        "# NosoGraph comparison",
        "",
        f"**Status:** `{result.status}`",
        "",
        "## Conditions",
        "",
    ]
    for curie in result.condition_curies:
        lines.append(f"- {_entity(result.condition_labels.get(curie, curie), curie)}")
    lines.extend(["", "## Dimensions", ""])
    lines.append(
        ", ".join(_escape(_DIMENSION_TITLES.get(item, item)) for item in result.dimensions)
        or "None"
    )
    lines.append("")

    for dimension in result.dimension_results:
        lines.extend(_render_dimension(result, dimension))

    lines.extend(["## Curation warnings", ""])
    if result.curation_warnings:
        lines.extend(f"- {_escape(item.message)}" for item in result.curation_warnings)
    else:
        lines.append("No curation warnings were recorded.")

    lines.extend(
        [
            "",
            "## Reproducibility",
            "",
            f"- **Run ID:** `{result.run_id}`",
            f"- **Result schema:** `{_escape(result.result_schema_version)}`",
            f"- **Algorithm:** `{_escape(result.algorithm_id)}` `{_escape(result.algorithm_version)}`",
            f"- **Claim-set fingerprint:** `{_escape(result.claim_set_fingerprint)}`",
            "- **Snapshot IDs:** "
            + (", ".join(f"`{item}`" for item in result.snapshot_ids) or "None"),
            "",
            "## Research-use disclaimer",
            "",
            f"> {_escape(result.disclaimer.text)}",
            "",
        ]
    )
    return "\n".join(lines).encode("utf-8")


def _render_dimension(
    result: NosoGraphCompareV2ResultView, dimension: DimensionComparisonView
) -> list[str]:
    title = _DIMENSION_TITLES.get(dimension.dimension, dimension.dimension)
    rows = {item.entity_curie: item for item in dimension.entities}
    lines = [f"## {_escape(title)}", "", "### Shared", ""]
    if dimension.dimension == "evidence_coverage":
        lines.append("This dimension summarizes evidence coverage rather than entity membership.")
    elif dimension.shared_by_all or dimension.shared_by_subset:
        for curie in dimension.shared_by_all:
            lines.append(f"- **All conditions:** {_row_entity(rows.get(curie), curie)}")
        for item in dimension.shared_by_subset:
            labels = ", ".join(
                _escape(result.condition_labels.get(curie, curie))
                for curie in item.condition_curies
            )
            lines.append(
                f"- **{labels}:** {_row_entity(rows.get(item.entity_curie), item.entity_curie)}"
            )
    else:
        lines.append("No shared entities were recorded.")

    lines.extend(["", "### Distinct", ""])
    distinct_found = False
    for condition_curie in result.condition_curies:
        entities = dimension.unique_by_condition.get(condition_curie, [])
        if not entities:
            continue
        distinct_found = True
        condition_label = result.condition_labels.get(condition_curie, condition_curie)
        rendered = ", ".join(_row_entity(rows.get(curie), curie) for curie in entities)
        lines.append(f"- **{_escape(condition_label)}:** {rendered}")
    if not distinct_found:
        lines.append("No condition-distinct entities were recorded.")

    lines.extend(["", "### Missing data", ""])
    missing_found = False
    for row in dimension.entities:
        cells = [
            f"{_escape(result.condition_labels.get(curie, curie))}: `{state}`"
            for curie, state in row.states.items()
            if state in {"KNOWN_ABSENT", "NOT_RECORDED"}
        ]
        if cells:
            missing_found = True
            lines.append(f"- {_entity(row.entity_label, row.entity_curie)} — {'; '.join(cells)}")
    if not missing_found:
        lines.append("No missing-data cells were recorded.")

    lines.extend(["", "### Evidence coverage", ""])
    lines.extend(
        [
            "| Condition | Claims | Positive | Negated | Evidence | Sources | Snapshots |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for curie in result.condition_curies:
        coverage = dimension.coverage_by_condition.get(curie)
        if coverage is None:
            continue
        label = _table(result.condition_labels.get(curie, curie))
        lines.append(
            f"| {label} | {coverage.claim_count} | {coverage.positive_claim_count} | "
            f"{coverage.negated_claim_count} | {coverage.evidence_count} | "
            f"{coverage.source_count} | {coverage.snapshot_count} |"
        )

    lines.extend(["", "### Warnings", ""])
    if dimension.warnings:
        lines.extend(f"- {_escape(item.message)}" for item in dimension.warnings)
    else:
        lines.append("No warnings were recorded for this dimension.")
    lines.append("")
    return lines


def _row_entity(row: EntityStateRowView | None, curie: str) -> str:
    return _entity(row.entity_label if row is not None else curie, curie)


def _entity(label: str, curie: str) -> str:
    safe_label = _escape(label or curie)
    safe_curie = _escape(curie)
    return f"{safe_label} (`{safe_curie}`)" if label and label != curie else f"`{safe_curie}`"


def _escape(value: object) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    for token in ("\\", "`", "*", "_", "[", "]", "<", ">", "#", "|"):
        text = text.replace(token, f"\\{token}")
    return text


def _table(value: object) -> str:
    return _escape(value).replace("\\|", "\\|")
