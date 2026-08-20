# Evidence Model

## Purpose

The Evidence Workspace assembles multi-source biomedical evidence into deterministic **claims** and ranked **hypotheses** for a research question and disease context.

**Maturity:** BETA — suitable for exploratory research, not clinical decision support.

## Core types

Defined in `pipeline/evidence_workspace/schemas.py`:

| Type | Role |
|------|------|
| `ResearchRequest` | Normalized user query + disease context |
| `EvidenceRecord` | Raw retrieval from a source adapter |
| `Claim` | Deterministic assertion extracted from evidence |
| `RankedCandidate` | Scored drug/target with explainable factors |
| `EvidenceDossier` | Aggregated output bundle |
| `GraphExplanation` | KG-backed rationale |
| `Citation` | Bibliographic / API reference |

## Source adapters

Adapters under `pipeline/evidence_workspace/sources/` and related modules:

| Source | Status |
|--------|--------|
| PubMed (Entrez) | STABLE |
| ClinicalTrials.gov v2 | STABLE |
| GWAS Catalog | BETA |
| FDA labels (openFDA) | BETA |
| Open Targets | BETA |
| GTEx, ChEMBL, bioRxiv | BETA (live connectors) |

Each adapter reports `SourceStatus` (fresh/stale/error).

## Claim generation

1. Adapters fetch normalized records.
2. Deterministic extractors produce claims (no LLM required).
3. Optional LLM enrichment (`OPENAI_API_KEY`) — **EXPERIMENTAL**, disabled by default in secure deployments.

## Deduplication & ranking

- `deduplicate_evidence()` merges near-duplicate records
- Ranking combines evidence strength, graph proximity, and configured weights
- Outputs include limitations and coverage warnings

## Integrity controls

| Control | Implementation |
|---------|----------------|
| Disease context isolation | `normalize_request()`, coverage checks |
| Provenance attachment | Shared `build_provenance()` |
| Secret-free metadata | Fingerprints exclude volatile fields |
| Research disclaimer | API + report templates |

## Relationship to disease KG

Evidence claims may reference entities in the per-disease JSON KG. The universal biomed store provides ontology-resolved identifiers for cross-disease comparison.

## Not implemented

- FHIR Evidence resource export (PLANNED)
- Phenopacket bundles (PLANNED)
- Real-world evidence ingestion (NOT_IMPLEMENTED)
