# P2 Wave 1 — Evidence Explorer Audit

**Wave:** P2 Wave 1 · Evidence Explorer Productization + Playwright Reliability  
**Status:** IMPLEMENTATION COMPLETE (branch `p2/wave1-evidence-explorer`, not yet merged)  
**Starting HEAD:** `c977d8b6b`  
**Implementation HEAD:** pending merge  
**Current release:** v2.3.0  
**Date:** 2026-08-21

---

## Executive summary

Wave 1 delivers a first-class **Evidence Explorer** research surface, structured evidence quality dimensions, hardened claim/evidence API contracts, Playwright reliability fixes, and deterministic browser coverage. Work is ready for PR review and hosted CI validation before v2.4.0 release prep.

**Recommended release readiness:** `READY_FOR_V2.4.0_RELEASE_PREP` (after merge + hosted green checks)

---

## PR plan (pre-merge)

| Workstream | Branch / PR title | Status |
|------------|-------------------|--------|
| Playwright reliability | `fix(test): stabilize Playwright UI harness` | Ready (CSS `.hidden`, structure API mock, serial `test-browser`) |
| Evidence contracts/API | `feat(evidence): harden evidence and provenance resources` | Ready |
| Evidence Explorer UI | `feat(evidence): add Evidence Explorer research experience` | Ready |
| Browser/API tests | `test(evidence): add browser and integration coverage` | Ready |

Suggested merge order: Playwright fixes → API/contracts → UI + tests (combined on branch).

---

## Playwright

### Previous baseline

- Documented slow suite: **12 passed / 10 failed** (structure-modal / intercept cluster; explorer tests not committed)
- `#structure-modal` visible on load due to missing global `.hidden` CSS

### Root causes addressed

| Classification | Fix |
|----------------|-----|
| `MODAL_OVERLAY_RACE` / `ACTUAL_UI_DEFECT` | Global `.modal-overlay.hidden { display: none }` |
| `NETWORK_INTERCEPT_RACE` | Mock `/api/v1/biomed/structures/*` in fixture backend |
| Missing explorer coverage | New `tests/test_evidence_explorer_ui.py` (4 scenarios) |

### Local validation

| Suite | Result |
|-------|--------|
| `tests/test_evidence_workspace_browser.py` | **11/11 passed** (serial, `-n 0`) |
| `tests/test_evidence_explorer_ui.py` | **4/4 passed** (serial, `-n 0`) |
| Combined single pytest invocation | Fixture conflict (dual session Playwright) — **Makefile runs two serial invocations** |

### Hosted run

Not yet dispatched post-implementation. Prior baseline run ID referenced in v2.3.0 audit.

---

## Evidence contract changes

### New

- `src/med_research/biomed/evidence_quality.py` — ADR-001 structured dimensions
- `EvidenceQualityView` on `ClaimEvidenceDetailView`
- `GET /api/v1/claims/{id}/related`
- Paginated `GET /api/v1/claims/{id}/evidence` with `limit`, `offset`, `sort`, `direction`, `source`, `species_context`
- `ClaimDetailView` counts: `supporting_count`, `contradictory_count`, `inconclusive_count`, `source_count`

### Compatibility

- v2.3.0 claim detail/provenance routes preserved
- Evidence list response shape changed from bare array → `PagedResponse` (**additive breaking change** for clients expecting a raw list; claim detail still embeds full evidence)

---

## Evidence Explorer capabilities

| Capability | Status |
|------------|--------|
| Claim summary (subject · predicate · object) | ✅ |
| Supporting / contradictory evidence groups | ✅ |
| Inconclusive handling | ✅ (claim-level summary; per-row INCONCLUSIVE when present) |
| Evidence quality badges | ✅ (derived dimensions) |
| Provenance timeline | ✅ |
| Source links (HTTPS validated) | ✅ |
| Filters + URL state | ✅ |
| Deep links (`?claim_id=`) | ✅ |
| Related claims | ✅ |
| Disease / condition integration | ✅ (Condition Explorer button + hero MONDO bridge) |
| JSON export link | ✅ (API resource) |
| Report data issue link | ✅ |

---

## Evidence quality dimensions

| Dimension | Implementation |
|-----------|----------------|
| `species_context` | Implemented (text inference) |
| `study_design` | Implemented (evidence_type hints) |
| `sample_size` | Implemented when present |
| `statistical_quality` | Implemented from confidence when present |
| `source_quality` / `origin_class` | Implemented from curator/extraction_method |
| `human_review` | Implemented from curator |
| `replication`, `effect_direction`, `directness`, `contradiction_burden` | Deferred (unknown) |

---

## Golden trace (tested)

```text
MONDO:0007915 (systemic lupus erythematosus)
  → GET /api/v1/conditions/MONDO:0007915/claims
  → claim_id (seeded fixture)
  → GET /api/v1/claims/{claim_id}
  → GET /api/v1/claims/{claim_id}/evidence
  → GET /api/v1/claims/{claim_id}/provenance
  → source_snapshot / ingestion → graph_claim
```

Verified by `tests/web/test_claim_provenance_api.py`.

---

## Scientific integrity

| Invariant | Enforced |
|-----------|----------|
| Association ≠ causation | Predicate badge, disclaimer copy |
| SUPPORTS ≠ CONTRADICTS | Separate UI groups + API `summary` |
| NOT_RECORDED ≠ KNOWN_ABSENT | Empty-state wording |
| ANIMAL ≠ HUMAN | `species_context` badge |
| GENERATED ≠ CURATED | `origin_class` badge |

---

## Tests

| Tier | Result |
|------|--------|
| Evidence quality unit | 3 passed |
| Claim/provenance API | 7 passed |
| Offline unit suite | passed (`-n 0`, browser tests excluded) |
| Browser (workspace) | 11 passed |
| Browser (explorer) | 4 passed |
| mypy (new modules) | clean on `evidence_quality.py`, `universal_service.py` |

---

## Known limitations

- Evidence quality inference is heuristic; sparse HPOA rows remain mostly `unknown`
- No hosted Playwright proof yet in this branch
- Evidence list pagination is a breaking shape change for direct list consumers
- UI smoke not yet promoted to required CI (`ui-smoke` job proposed, not configured)
- Compare V2 explicitly out of scope

---

## Beta criteria progress

| Criterion | Progress |
|-----------|----------|
| Evidence Explorer usable | **Advanced** (Wave 1 UI shipped) |
| Playwright slow suite reliable | **Advanced** (local green; hosted TBD) |
| Public demo | Not started |
| Compare V2 + exports | Not started |

---

## Documentation

- [Evidence Explorer architecture](architecture/evidence-explorer.md)
- ROADMAP update pending merge

---

## v2.4.0 readiness

**Recommendation:** `READY_FOR_V2.4.0_RELEASE_PREP` after PR merge and one green hosted slow/browser workflow run.

**Theme:** NosoGraph v2.4.0 — Evidence Explorer
