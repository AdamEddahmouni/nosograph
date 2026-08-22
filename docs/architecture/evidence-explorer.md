# Evidence Explorer Architecture

**Status:** P2 Wave 1 · PUBLIC_ALPHA  
**Baseline release:** v2.4.0

## Purpose

Evidence Explorer answers **why NosoGraph says this** for any supported biomedical claim. It is a read-only research surface backed by normalized `/api/v1` resources — not a source-specific JSON viewer.

## Resource flow

```text
external source → adapter → normalized record → evidence ledger → claim → API → Evidence Explorer
```

## Canonical API routes

| Route | Purpose |
|-------|---------|
| `GET /api/v1/claims/{claim_id}` | Claim summary + inline evidence + provenance |
| `GET /api/v1/claims/{claim_id}/evidence` | Paginated/filtered evidence list |
| `GET /api/v1/claims/{claim_id}/provenance` | Machine-readable provenance chain |
| `GET /api/v1/claims/{claim_id}/related` | Related claims (same subject/object) |
| `GET /api/v1/conditions/{curie}/claims` | Condition-scoped claim discovery |

## Evidence quality (ADR-001)

Structured dimensions live in `biomed/evidence_quality.py` and serialize as `quality` on each evidence row. Missing metadata remains `unknown` — absence is not treated as low quality.

Implemented dimensions:

- `species_context` (human / animal / in_vitro / computational / unknown)
- `study_design`, `sample_size`, `statistical_quality` (when derivable)
- `source_quality`, `origin_class`, `human_review`
- `limitations[]`

Not inferred in Wave 1: replication, effect direction, directness, contradiction burden.

## Scientific invariants

| Invariant | UI behavior |
|-----------|-------------|
| Association ≠ causation | Predicate badge shows exact relationship type |
| SUPPORTS ≠ CONTRADICTS | Separate groups; mixed claim → INCONCLUSIVE summary |
| NOT_RECORDED ≠ KNOWN_ABSENT | Empty states say “not recorded in current dataset” |
| ANIMAL ≠ HUMAN | Species badge on evidence rows |
| GENERATED ≠ CURATED | `origin_class` badge |

## UI surfaces

- **Nav:** `#evidence-explorer`
- **Deep link:** `?claim_id={uuid}#evidence-explorer`
- **Condition bridge:** Condition Explorer claim rows → “Open in Evidence Explorer”
- **Disease bridge:** Hero link routes to mapped MONDO CURIE via Condition Explorer

## Filters & URL state

Evidence list filters sync to query params:

- `evidence_direction`
- `evidence_species`
- `evidence_sort` (`newest` | `oldest` | `source`)

## Provenance stages

Per evidence item: `source_snapshot` → `normalized_record`  
Per claim chain: `ingestion` (deduped snapshots) → `graph_claim`

## Test fixtures

Browser tests use explicit synthetic contradictory evidence marked `synthetic_test_fixture = true` in limitations. Synthetic fixtures never enter production datasets.
