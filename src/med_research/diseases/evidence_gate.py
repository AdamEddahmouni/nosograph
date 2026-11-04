"""Evidence-density gate for disease knowledge-graph records.

Structural validity answers "can this module be loaded and used?" Evidence
density answers a different question: "does each gene, drug, and pathway
record carry at least one resolvable provenance identifier?" A module can be
structurally valid and wholly unevidenced; this module keeps those two
statements separate and never turns missing citations into a structural
failure.

A record counts as evidenced only when its ``references`` list contains a
recognised identifier scheme. The record's own ``id`` is deliberately not
counted: an entity identifier says what the record is about, not what supports
the claim. Free-text notes are recorded as ``UNCLASSIFIED`` and do not count.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

#: Minimum share of gene, drug, and pathway records that must carry at least
#: one resolvable identifier before the evidence gate passes.
EVIDENCE_DENSITY_TARGET = 0.80

EVIDENCE_SCOPE = "gene, drug, and pathway records"
EVIDENCE_DEFINITION = (
    "A record is evidenced when its `references` list contains at least one "
    "recognised identifier scheme (for example PMID, DOI, CLINVAR, NCT, or "
    "CHEMBL). The record's own `id` is not counted: it identifies the entity, "
    "not the evidence for the claim."
)

#: Identifier schemes that resolve to an external record. ``OTHER`` and
#: ``UNCLASSIFIED`` are intentionally absent; they are reported but never
#: counted as provenance.
RESOLVABLE_SCHEMES: frozenset[str] = frozenset(
    {
        "PMID",
        "PMC",
        "DOI",
        "NCT",
        "REACTOME",
        "KEGG",
        "OMIM",
        "MONDO",
        "EFO",
        "HP",
        "ORPHA",
        "CHEMBL",
        "DRUGBANK",
        "UNIPROT",
        "CLINVAR",
        "GO",
    }
)

# Backwards-compatible name used by the evidence-coverage report.
KNOWN_REFERENCE_SCHEMES = RESOLVABLE_SCHEMES

_LEADING_SCHEME = re.compile(r"^([A-Za-z][A-Za-z0-9]{1,15})\s*[:_]")
_EMBEDDED_SCHEME = re.compile(
    r"\b(PMID|NCT|DOI|CLINVAR|ORPHA|CHEMBL|DRUGBANK)\s*[:_]?\s*\d",
    re.IGNORECASE,
)


def reference_schemes(reference: Any) -> list[str]:
    """Return the identifier schemes a single reference string declares.

    The leading token wins when it is a recognised prefix; embedded
    identifiers are added too, because free-text citations such as
    ``"ACR 2024 Abstract; REGENCY Trial (NCT04252599)"`` do carry a resolvable
    trial identifier. Unrecognised text is reported as ``UNCLASSIFIED`` rather
    than being treated as provenance.
    """
    text = str(reference).strip()
    if not text:
        return ["UNCLASSIFIED"]
    schemes: list[str] = []
    leading = _LEADING_SCHEME.match(text)
    if leading:
        token = leading.group(1).upper()
        schemes.append(token if token in RESOLVABLE_SCHEMES else "OTHER")
    for embedded in _EMBEDDED_SCHEME.findall(text):
        token = embedded.upper()
        if token not in schemes:
            schemes.append(token)
    return schemes or ["UNCLASSIFIED"]


def is_resolvable_reference(reference: Any) -> bool:
    """Return whether a reference value names a recognised external record."""
    return any(scheme in RESOLVABLE_SCHEMES for scheme in reference_schemes(reference))


def _record_is_evidenced(record: Mapping[str, Any]) -> bool:
    raw = record.get("references")
    if raw is None:
        return False
    values = raw if isinstance(raw, (list, tuple, set)) else [raw]
    return any(is_resolvable_reference(value) for value in values)


def summarize_evidence(
    records: int,
    evidenced: int,
    *,
    structurally_valid: bool | None = None,
    assessed: bool = True,
    errors: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Build the canonical evidence block shared by all report surfaces."""
    records = max(int(records), 0)
    evidenced = min(max(int(evidenced), 0), records)
    density = round(evidenced / records, 4) if records else 0.0
    return {
        "assessed": assessed,
        "scope": EVIDENCE_SCOPE,
        "definition": EVIDENCE_DEFINITION,
        "records": records,
        "evidenced": evidenced,
        "without_resolvable_identifier": records - evidenced,
        "density": density,
        "target": EVIDENCE_DENSITY_TARGET,
        # Zero records is not a pass: an empty collection is not evidence.
        "passes": bool(records) and density >= EVIDENCE_DENSITY_TARGET,
        "structurally_valid": structurally_valid,
        "errors": dict(errors or {}),
    }


def assess_records(collections: Mapping[str, Sequence[Any]]) -> dict[str, Any]:
    """Measure evidence density across named record collections.

    ``collections`` is keyed by collection name (``genes``, ``drugs``,
    ``pathways``) and each value is a sequence of record mappings. Non-mapping
    entries are ignored rather than counted as evidenced.
    """
    by_collection: dict[str, dict[str, Any]] = {}
    total_records = 0
    total_evidenced = 0

    for key, items in collections.items():
        records = [item for item in items if isinstance(item, Mapping)]
        evidenced = sum(1 for record in records if _record_is_evidenced(record))
        count = len(records)
        total_records += count
        total_evidenced += evidenced
        by_collection[key] = {
            "records": count,
            "evidenced": evidenced,
            "without_resolvable_identifier": count - evidenced,
            "density": round(evidenced / count, 4) if count else 0.0,
            "passes": bool(count) and (evidenced / count) >= EVIDENCE_DENSITY_TARGET,
        }

    summary = summarize_evidence(total_records, total_evidenced)
    summary["by_collection"] = dict(sorted(by_collection.items()))
    return summary


def assess_disease(disease: Any) -> dict[str, Any]:
    """Measure evidence density for a disease module's three KG collections.

    Loading is deliberately fail-closed: a collection that cannot be read is
    reported in ``errors`` and the gate cannot pass. Structural validation
    remains a separate result and is supplied by the caller.
    """
    accessors = {
        "genes": "load_genes",
        "drugs": "load_drugs",
        "pathways": "load_pathways",
    }
    collections: dict[str, list[Any]] = {}
    errors: dict[str, str] = {}

    for key, accessor in accessors.items():
        try:
            payload = getattr(disease, accessor)()
            items = payload.get(key) if isinstance(payload, Mapping) else None
            if not isinstance(items, list):
                raise TypeError(f"{accessor}() did not return a '{key}' list")
            collections[key] = items
        except Exception as exc:  # noqa: BLE001 - reported, never swallowed
            collections[key] = []
            errors[key] = f"{type(exc).__name__}: {exc}"

    summary = assess_records(collections)
    if errors:
        summary["assessed"] = False
        summary["errors"] = errors
        summary["passes"] = False
    return summary


__all__ = [
    "EVIDENCE_DEFINITION",
    "EVIDENCE_DENSITY_TARGET",
    "EVIDENCE_SCOPE",
    "KNOWN_REFERENCE_SCHEMES",
    "RESOLVABLE_SCHEMES",
    "assess_disease",
    "assess_records",
    "is_resolvable_reference",
    "reference_schemes",
    "summarize_evidence",
]
