# P2 Wave 1 — Evidence Explorer Audit

**Wave:** P2 Wave 1 · Evidence Explorer Productization + Playwright Reliability  
**Status:** SHIPPED_IN_V2.4.0  
**Starting HEAD:** `c977d8b6b`  
**Wave 1 implementation:** `5e9a317c6`  
**Integration base (master):** `4e6bf2a5b`  
**Final merge SHA:** `27d7d1ebe` (PR #22)  
**Release:** v2.4.0 (2026-08-22)  
**Date:** 2026-08-22

---

## Executive summary

Wave 1 delivers a first-class **Evidence Explorer** research surface, structured evidence quality dimensions, hardened claim/evidence API contracts, Playwright reliability fixes, and deterministic browser coverage. Integrated with post-public-presence master (PR #23/#24) via merge; hosted CI and browser proof green.

**Release readiness:** `SHIPPED_IN_V2.4.0`

---

## Integration

| Item | Value |
|------|-------|
| Strategy | `MERGE_MASTER_INTO_WAVE1` |
| Conflicts | `Makefile` only (merged `test-browser` + `docs-serve`/`check-public-metadata`) |
| Pre-sync backup | `backup/p2-wave1-pre-master-sync` at `5e9a317c6` |

---

## Playwright

### Local validation

| Suite | Result |
|-------|--------|
| `tests/test_evidence_workspace_browser.py` | **11/11 passed** (serial, `-n 0`) |
| `tests/test_evidence_explorer_ui.py` | **4/4 passed** (serial, `-n 0`) |

### Hosted validation

| Run | Result |
|-----|--------|
| [32547140215](https://github.com/AdamEddahmouni/nosograph/actions/runs/32547140215) slow-tests | **PASS** (includes Playwright browser subset) |

---

## API compatibility decision

**`BREAKING_CHANGE_ACCEPTED`**

`GET /api/v1/claims/{id}/evidence` changed from bare list → `PagedResponse`. In-repo frontend, tests, and docs updated. Claim detail still embeds inline evidence. Documented in CHANGELOG and release notes.

---

## Evidence contract changes

- `src/med_research/biomed/evidence_quality.py` — ADR-001 structured dimensions
- `EvidenceQualityView` on `ClaimEvidenceDetailView`
- `GET /api/v1/claims/{id}/related`
- Paginated evidence list with filters
- Claim detail counts: `supporting_count`, `contradictory_count`, `inconclusive_count`, `source_count`

---

## Evidence Explorer capabilities

| Capability | Status |
|------------|--------|
| Claim summary | ✅ |
| Supporting / contradictory / inconclusive groups | ✅ |
| Evidence quality badges | ✅ |
| Provenance timeline | ✅ |
| Source links | ✅ |
| Filters + URL state | ✅ |
| Deep links | ✅ |
| Related claims | ✅ |
| Condition integration | ✅ |
| JSON/API export link | ✅ |

---

## Evidence quality dimensions

| Dimension | Implementation |
|-----------|----------------|
| `species_context` | Implemented (conservative text inference) |
| `study_design` | Implemented (evidence_type hints; no bare "trial" → RCT) |
| `sample_size` | Implemented when present |
| `statistical_quality` | Text hints only; **not** inferred from confidence scores (v2.4.0 tightening) |
| `source_quality` / `origin_class` | Implemented from curator/extraction_method |
| `human_review` | Implemented from curator |
| `replication`, `effect_direction`, `directness`, `contradiction_burden` | Deferred (`unknown`) |

---

## Golden trace

```text
MONDO:0007915 → claims → claim_id → evidence (paginated) → provenance
```

Verified by `tests/web/test_claim_provenance_api.py`.

---

## Scientific integrity

| Invariant | Enforced |
|-----------|----------|
| Association ≠ causation | Predicate badge, disclaimer |
| SUPPORTS ≠ CONTRADICTS | Separate groups + API `summary` |
| NOT_RECORDED ≠ KNOWN_ABSENT | Empty-state wording |
| ANIMAL ≠ HUMAN | `species_context` badge |
| GENERATED ≠ CURATED | `origin_class` badge |
| UNKNOWN ≠ LOW_QUALITY | Default `unknown` dimensions |

---

## Tests

| Tier | Result |
|------|--------|
| Evidence quality unit | 3 passed |
| Claim/provenance API | 7 passed |
| Workspace browser | 11 passed |
| Explorer browser | 4 passed |
| PR #22 required CI | PASS (typecheck informational fail) |

---

## Known limitations

- Heuristic evidence-quality inference; sparse metadata remains `unknown`
- No public hosted demo
- Compare V2 out of scope (Wave 2)

---

## Documentation

- [User guide](../using/evidence-explorer.md)
- [Architecture](../architecture/evidence-explorer.md)

---

## v2.4.0

**Status:** `RELEASED` — see [v2.4.0 release record](v2.4.0-release.md) and [release notes](../release-notes/v2.4.0.md).
