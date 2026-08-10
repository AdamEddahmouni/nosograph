"""Claim extraction with deterministic-first and optional LLM enrichment."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from typing import Any, cast

from med_research.pipeline.knowledge_graph.config import load_drugs, load_genes, load_pathways

from .schemas import Citation, Claim, EvidenceRecord


def _entity_catalog(disease_id: str) -> dict[str, dict[str, dict[str, Any]]]:
    genes = {item["id"]: dict(item) for item in load_genes(disease_id).get("genes", [])}
    drugs = {item["id"]: dict(item) for item in load_drugs(disease_id).get("drugs", [])}
    pathways = {item["id"]: dict(item) for item in load_pathways(disease_id).get("pathways", [])}
    return {"genes": genes, "drugs": drugs, "pathways": pathways}


def _aliases(item: dict[str, Any], entity_id: str) -> set[str]:
    aliases = {entity_id.lower(), str(item.get("name", "")).lower()}
    name = str(item.get("name", ""))
    if "(" in name:
        aliases.add(name.split("(", 1)[0].strip().lower())
    return {alias for alias in aliases if len(alias) >= 3}


def _find_entities(
    text: str, catalogs: dict[str, dict[str, dict[str, Any]]]
) -> list[tuple[str, str, str]]:
    lowered = text.lower()
    found = []
    for entity_type, items in catalogs.items():
        subject_type = "target" if entity_type == "genes" else entity_type[:-1]
        for entity_id, item in items.items():
            if any(
                re.search(rf"(?<![\w-]){re.escape(alias)}(?![\w-])", lowered)
                for alias in _aliases(item, entity_id)
            ):
                found.append((entity_id, subject_type, str(item.get("name", entity_id))))
    return found


_VARIANT_PATTERN = re.compile(r"\brs\d{4,}\b", re.IGNORECASE)
_OUTCOME_PATTERN = re.compile(
    r"\b(?:SRI[- ]?4|BICLA|remission|response|flare|relapse|disease activity)\b",
    re.IGNORECASE,
)


def _polarity(text: str) -> str:
    lowered = text.lower()
    contradiction_terms = (
        "failed",
        "did not meet",
        "no significant",
        "negative trial",
        "ineffective",
        "not improve",
    )
    return "contradicts" if any(term in lowered for term in contradiction_terms) else "supports"


def _evidence_type(record: EvidenceRecord) -> str:
    value = record.evidence_type.lower()
    if "phase" in value or record.source == "clinical_trials":
        return "clinical_trial"
    return record.evidence_type


def _confidence(
    record: EvidenceRecord, method: str, conflict: bool = False
) -> tuple[float, dict[str, float]]:
    quality = 0.75 if record.source == "pubmed" else 0.8
    if record.evidence_type.lower() in {"rct", "phase 3", "phase3", "clinical_trial"}:
        quality = 0.9
    recency = 1.0
    if record.published_date:
        age = max(0, date.today().year - record.published_date.year)
        recency = max(0.25, 1.0 - age / 20)
    method_score = 0.8 if method == "rules" else 0.65
    conflict_penalty = 0.7 if conflict else 1.0
    components = {
        "source_quality": quality,
        "recency": recency,
        "extraction": method_score,
        "conflict_adjustment": conflict_penalty,
    }
    return round(
        max(
            0.0,
            min(1.0, quality * 0.4 + recency * 0.2 + method_score * 0.2 + conflict_penalty * 0.2),
        ),
        3,
    ), components


def _citation(record: EvidenceRecord) -> Citation:
    return Citation(
        source=record.source,
        native_id=record.native_id,
        title=record.title,
        doi=record.doi,
        url=record.url,
        published_date=record.published_date,
    )


def extract_deterministic(records: list[EvidenceRecord], disease_id: str) -> "ExtractionResult":
    catalog = _entity_catalog(disease_id)
    claims: list[Claim] = []
    for record in records:
        text = f"{record.title}. {record.snippet}"
        polarity = _polarity(text)
        for entity_id, subject_type, subject_name in _find_entities(text, catalog):
            if subject_type == "drug":
                relationship = (
                    polarity if polarity in ("supports", "contradicts") else "associated_with"
                )
            elif subject_type == "target":
                relationship = "associated_with" if polarity == "supports" else "contradicts"
            else:
                relationship = "associated_with"
            confidence, components = _confidence(record, "rules")
            claims.append(
                Claim(
                    claim_id=f"rules:{record.evidence_id}:{entity_id}:{relationship}",
                    subject_id=entity_id,
                    subject_type=cast(Any, subject_type),
                    subject_name=subject_name,
                    relationship=cast(Any, relationship),
                    text=f"{subject_name} is mentioned in evidence titled '{record.title}'.",
                    evidence_ids=[record.evidence_id],
                    citations=[_citation(record)],
                    supporting_snippet=record.snippet[:800],
                    evidence_type=_evidence_type(record),
                    confidence=confidence,
                    confidence_components=components,
                    extraction_method="rules",
                    limitations=[
                        "Entity and relationship are pattern-based; inspect the cited source context."
                    ],
                )
            )
        for match in _VARIANT_PATTERN.finditer(text):
            variant_id = match.group(0).lower()
            confidence, components = _confidence(record, "rules")
            claims.append(
                Claim(
                    claim_id=f"rules:{record.evidence_id}:{variant_id}:associated_with",
                    subject_id=variant_id,
                    subject_type="variant",
                    subject_name=match.group(0),
                    relationship="associated_with",
                    text=f"Variant {match.group(0)} is mentioned in evidence titled '{record.title}'.",
                    evidence_ids=[record.evidence_id],
                    citations=[_citation(record)],
                    supporting_snippet=record.snippet[:800],
                    evidence_type=_evidence_type(record),
                    confidence=confidence,
                    confidence_components=components,
                    extraction_method="rules",
                    limitations=["Variant interpretation requires review of the cited study."],
                )
            )
        for match in _OUTCOME_PATTERN.finditer(text):
            outcome_id = re.sub(r"[^a-z0-9]+", "_", match.group(0).lower()).strip("_")
            if outcome_id in {"response", "remission", "flare", "relapse", "disease_activity"}:
                outcome_id = (
                    "sri-4_response"
                    if outcome_id == "response" and "sri" in text.lower()
                    else outcome_id
                )
            confidence, components = _confidence(record, "rules")
            claims.append(
                Claim(
                    claim_id=f"rules:{record.evidence_id}:{outcome_id}:associated_with",
                    subject_id=outcome_id,
                    subject_type="outcome",
                    subject_name=match.group(0),
                    relationship="associated_with",
                    text=f"Outcome {match.group(0)} is mentioned in evidence titled '{record.title}'.",
                    evidence_ids=[record.evidence_id],
                    citations=[_citation(record)],
                    supporting_snippet=record.snippet[:800],
                    evidence_type=_evidence_type(record),
                    confidence=confidence,
                    confidence_components=components,
                    extraction_method="rules",
                    limitations=[
                        "Outcome meaning and magnitude require review of the cited study."
                    ],
                )
            )
    grouped: dict[tuple[str, str], list[Claim]] = defaultdict(list)
    for claim in claims:
        grouped[(claim.subject_id, claim.subject_type)].append(claim)
    for (subject_id, subject_type), related in grouped.items():
        relationships = {claim.relationship for claim in related}
        if "supports" in relationships and "contradicts" in relationships:
            conflict_group = f"conflict:{subject_type}:{subject_id}"
            for claim in related:
                claim.conflict_group = conflict_group
                confidence, components = _confidence(
                    next(record for record in records if record.evidence_id in claim.evidence_ids),
                    claim.extraction_method,
                    conflict=True,
                )
                claim.confidence = confidence
                claim.confidence_components = components
    return ExtractionResult(claims=claims, warnings=[], llm_status="not_requested")


class ExtractionResult:
    def __init__(self, claims: list[Claim], warnings: list[str], llm_status: str):
        self.claims = claims
        self.warnings = warnings
        self.llm_status = llm_status


def _validate_llm_claim(
    item: Any,
    records: dict[str, EvidenceRecord],
    model: str | None,
    disease_id: str = "sle",
) -> Claim | None:
    if not isinstance(item, dict):
        return None
    evidence_ids = item.get("evidence_ids")
    if (
        not isinstance(evidence_ids, list)
        or not evidence_ids
        or any(eid not in records for eid in evidence_ids)
    ):
        return None
    subject_type = item.get("subject_type")
    if subject_type == "gene":
        subject_type = "target"
    if subject_type not in {"drug", "target", "pathway", "variant", "outcome", "other"}:
        return None
    catalog = _entity_catalog(disease_id)
    known_ids = set(catalog["drugs"]) | set(catalog["genes"]) | set(catalog["pathways"])
    if str(item.get("subject_id", "")) not in known_ids:
        return None
    source_record = records[evidence_ids[0]]
    confidence, components = _confidence(source_record, "llm")
    return Claim(
        claim_id=str(item.get("claim_id") or f"llm:{evidence_ids[0]}:{item.get('subject_id', '')}"),
        subject_id=str(item.get("subject_id", "")),
        subject_type=subject_type,
        subject_name=str(item.get("subject_name", item.get("subject_id", ""))),
        relationship=item.get("relationship", "associated_with"),
        text=str(item.get("text", "")),
        evidence_ids=evidence_ids,
        citations=[_citation(records[eid]) for eid in evidence_ids],
        supporting_snippet=str(item.get("supporting_snippet", source_record.snippet[:800])),
        evidence_type=source_record.evidence_type,
        confidence=confidence,
        confidence_components=components,
        extraction_method="llm",
        model_name=model,
        limitations=["LLM-generated interpretation; verify against the cited source."],
    )


def enrich_with_llm(
    records: list[EvidenceRecord],
    existing_claims: list[Claim],
    llm_client: Any = None,
    model: str | None = None,
    disease_id: str = "sle",
) -> ExtractionResult:
    if llm_client is None:
        return ExtractionResult([], ["LLM enrichment skipped: no client configured."], "skipped")
    try:
        raw_claims = llm_client.extract(records, existing_claims, model=model)
        indexed = {record.evidence_id: record for record in records}
        claims = []
        invalid = 0
        for item in raw_claims or []:
            claim = _validate_llm_claim(item, indexed, model, disease_id)
            if claim is None:
                invalid += 1
            else:
                claims.append(claim)
        warnings = [f"LLM enrichment discarded {invalid} invalid claim(s)."] if invalid else []
        return ExtractionResult(claims, warnings, "completed")
    except Exception as exc:  # optional integration must not block deterministic output
        return ExtractionResult(
            [], [f"LLM enrichment failed: {type(exc).__name__}: {exc}"], "failed"
        )


def extract_claims(
    records: list[EvidenceRecord],
    disease_id: str,
    enable_llm: bool = True,
    llm_client: Any = None,
    model: str | None = None,
) -> ExtractionResult:
    deterministic = extract_deterministic(records, disease_id)
    if not enable_llm:
        deterministic.llm_status = "disabled"
        return deterministic
    enriched = enrich_with_llm(records, deterministic.claims, llm_client, model, disease_id)
    deterministic.claims.extend(enriched.claims)
    deterministic.warnings.extend(enriched.warnings)
    deterministic.llm_status = enriched.llm_status
    return deterministic
