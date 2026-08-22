# NosoGraph P2 Master Plan

**Theme:** Evidence-Native Research Experience  
**Baseline:** v2.3.0 (`ff1ea223b`) · PUBLIC_ALPHA  
**Status:** APPROVED FOR IMPLEMENTATION  
**Owner:** NosoGraph core team  
**Last updated:** 2026-08-22

---

## 1. Objectives

Transform NosoGraph from a credible alpha platform into a **research product** where:

1. Every displayed claim is explorable to supporting/contradicting evidence and original sources
2. Disease comparison is a standalone, exportable workflow with honest missingness
3. A public read-only demo showcases these differentiators safely
4. Shared domain contracts prevent duplicate schemas across modules

## 2. Non-goals (P2)

- Clinical decision support or patient-facing products
- Full 10k scaffold curation
- FHIR / OMOP / billing / SaaS deployment
- Boolean/ODE/computational model execution platform
- Autonomous hypothesis publication without review gates
- Package rename to `nosograph` on PyPI (defer to v3.0 unless PyPI ships earlier)

---

## 3. Architecture boundaries (preserve)

```
external source → adapter → normalized schema → evidence ledger → knowledge graph → compute services → APIs → product surfaces
```

**Rules:**

- UI never imports source-specific schemas
- Hypotheses never write into canonical evidence graph as facts
- Generated outputs carry `generation_state` and `curation_state`
- Missing data ≠ known absent (enforced in Compare and Explorer)

---

## 4. Shared domain contracts (implement in Wave 1)

These become authoritative before parallel UI work:

| Contract | Location (target) | Consumers |
|----------|-------------------|-----------|
| `ClaimView` | `biomed/models.py` + `web/models/universal.py` | Explorer, Compare drill-down, API |
| `EvidenceQuality` | new `biomed/evidence_quality.py` | Explorer filters, contradiction prep |
| `EvidenceSummaryLiteral` | already exists | Normalize workspace vocabulary |
| `ComparisonResult` | `nosograph_compare/models.py` | Compare V2, exports |
| `Missingness` | `nosograph_compare/models.py` | Compare, gap engine prep |
| `ProvenanceChain` | `web/models/universal.py` | Explorer drawer |
| `CurationLevel` | `diseases/curation_tiers.py` | Atlas, demo, picker |
| `SourceRef` | `biomed/models.py` | Explorer source links |

**ADR-001:** Evidence Quality Model (Wave 1 gate)  
**ADR-002:** Evidence Explorer resource model (Wave 1 gate)  
**ADR-003:** [Compare V2 semantics](../architecture/decisions/003-compare-v2-semantics.md) — Accepted (Wave 2 gate)

---

## 5. Evidence Quality Model (ADR-001)

Structured dimensions (no single opaque score):

| Dimension | Values |
|-----------|--------|
| `species_context` | human, animal, in_vitro, computational |
| `study_design` | rct, cohort, case_control, case_series, review, unknown |
| `sample_size` | integer or unknown |
| `replication` | replicated, single_study, unknown |
| `effect_direction` | positive, negative, null, mixed, unknown |
| `statistical_quality` | high, medium, low, unknown |
| `directness` | direct, indirect, unknown |
| `source_quality` | curated, imported, generated, unknown |
| `recency` | ISO date |
| `human_review` | none, community, expert |
| `contradiction_burden` | none, some, high |

Populate from existing evidence metadata where possible; default to `unknown` rather than invent.

---

## 6. Epics

### Epic E1 — Evidence Explorer (P0)

**Why:** Core brand promise; P1-D backend complete, UX incomplete.  
**Dependencies:** ADR-001, ADR-002, shared `ClaimView`  
**Effort:** M · **Risk:** medium

**Scope:**

- Unified Explorer nav section (not buried in Condition Explorer)
- Claim summary with SUPPORTS/CONTRADICTS/INCONCLUSIVE aggregate
- Evidence drawer: supporting, contradicting, inconclusive lists
- Filters: evidence type, species, study design, date, source, direction
- Provenance chain visualization (ingestion → normalized → graph_claim)
- Source link (HPOA, OT, legacy snapshot, workspace record)
- Curation/generation badges
- Related claims panel

**Definition of done:**

```
User opens claim from disease/condition context
→ sees evidence summary counts
→ filters evidence list
→ opens provenance chain
→ clicks through to original source metadata/URL
→ sees evidence-quality context per row
→ tests cover API serialization + UI smoke
→ no source-specific UI components (adapter-agnostic views)
```

**Key files:**

- `web/static/js/dashboard.js` (Explorer module)
- `web/static/index.html` (nav + section)
- `web/services/universal_service.py`
- `web/routers/universal.py`
- `tests/web/test_claim_provenance_api.py` (extend)
- `tests/test_evidence_explorer_ui.py` (new Playwright)

---

### Epic E2 — Compare V2 Product (P0)

**Why:** Second flagship differentiator; the Sprint 1 engine and API exist, but the standalone
product workflow does not.
**Dependencies:** E1 drill-down, ADR-003  
**Effort:** M · **Risk:** medium

**Current state (2026-08-22):** Sprint 1 backend is complete: ADR-003 is accepted; deterministic
2–5-condition comparison, all five dimensions, explicit absence states, curation warnings,
research-run replay, the canonical API, the deprecated pairwise adapter, and golden JSON tests
are implemented. UI, exports, CLI support, and Explorer drill-down remain future work.

**V2 dimensions (data-backed only):**

| Dimension | Include P2 | Rationale |
|-----------|------------|-----------|
| phenotype | yes | HPOA claims abundant |
| gene | yes | OT + legacy |
| pathway | yes | `INVOLVES_PATHWAY` |
| treatment | yes | TREATED_BY |
| evidence_coverage | yes | per-condition claims, evidence, sources, and snapshots |
| biomarker | defer | schema immature |
| trials | P2 P1 | after trials sync |
| cells/anatomy | defer | sparse claims |
| epidemiology | reject | no structured data |

**Workflow:**

```
Select 2–5 diseases (MONDO CURIEs)
→ Select dimensions
→ Summary (shared / distinct / missing per dimension)
→ Shared biology panel
→ Distinct biology panel
→ Evidence strength summary (linked to Explorer)
→ Curation asymmetry warnings
→ Export JSON + Markdown report
→ Optional: save to workspace run
```

**Definition of done:**

```
User selects 3 diseases, 5 dimensions
→ sees explicit NOT_RECORDED vs KNOWN_ABSENT labels
→ clicks shared gene → opens Evidence Explorer for claim
→ exports comparison report
→ API returns deterministic JSON for same inputs + snapshot versions
→ tests: engine multi-disease + API + export golden files
```

**Key files:**

- `biomed/nosograph_compare/engine.py`, `service.py`, `models.py`
- `web/services/nosograph_compare_service.py`
- `web/routers/universal.py`
- `tests/biomed/nosograph_compare/`

---

### Epic E3 — Playwright & Demo-Blocking Debt (P0)

**Why:** 45% slow-suite failure rate; blocks public demo confidence.  
**Dependencies:** none  
**Effort:** S · **Risk:** low

**Actions:**

1. Extend `_FixtureBackend` mocks for `/api/v1/biomed/structures/*`, corpus status, biomed import status
2. Stabilize WebSocket→polling fallback timeouts for CI
3. Split Playwright job from live-network slow tests OR mark live tests `@pytest.mark.live`
4. Fix `structure-modal` intercept race

**Definition of done:**

```
slow-tests Playwright subset ≥90% pass on hosted CI (3 consecutive runs)
structure-modal tests pass without retry hacks
PR gate unchanged (Playwright remains slow tier)
```

---

### Epic E4 — Public Read-Only Demo (P1)

**Why:** Adoption, beta criterion, showcases differentiators.  
**Dependencies:** E1, E2, E3  
**Effort:** M · **Risk:** medium

**Architecture:**

| Component | Spec |
|-----------|------|
| `DEMO_MODE=true` | Disables writes: workspace submit, jobs POST, admin |
| Dataset | Prebuilt `biomedical.sqlite3` + 8 ci_validated modules + MONDO/HPO/HPOA fixtures |
| Routes exposed | Home, Atlas (tier-filtered), Disease, Evidence, Compare, Sources, About |
| Hidden | Admin, prune/restore, agent write, LLM extraction |
| Ops | Docker Compose, Redis read-only cache, rate limits, CSP strict |
| Observability | `/api/health`, structured logs, no secrets in env |

**Definition of done:**

```
DEMO_MODE deployment serves Explorer + Compare on fixed dataset
anonymous user cannot mutate state (verified by integration tests)
rate limit triggers gracefully
documentation: docs/deployment-demo.md
```

---

### Epic E5 — Source Sync Expansion (P1)

**Why:** Depth for Compare and Explorer.  
**Dependencies:** sync lifecycle (exists)  
**Effort:** M · **Risk:** medium

**Wave 4 targets:**

1. HPOA automated sync (phenotype claims)
2. MONDO release sync (identity)
3. ClinicalTrials.gov structured import (trials dimension prep)

Each requires: hosted dry-run workflow, offline fixtures, provenance update, licensing note in `data/sources/registry.yaml`.

---

### Epic E6 — Literature Intelligence Foundation (P1)

**Why:** Long-term differentiator; workspace extraction exists.  
**Dependencies:** E1, corpus ADR  
**Effort:** L · **Risk:** high

**Scope (foundation only):**

- Persistent literature metadata store (SQLite table, not full text corpus)
- PubMed/Europe PMC ingest with snapshot versioning
- Deterministic claim extraction pipeline (extend workspace `extraction.py`)
- Review status on every extracted claim
- No unsourced LLM summaries in product UI

---

### Epic E7 — Contradiction Engine (P2 defer)

Contextual disagreement model:

```
claim_a, claim_b, comparison_context, contradiction_type,
population_diff, method_diff, stage_diff, effect_direction, confidence
```

Requires E1 + Evidence Quality Model. Not P2 P0.

---

### Epic E8 — Knowledge Gap Engine (P2 defer)

Gap categories: `MISSING_EVIDENCE`, `WEAK_REPLICATION`, `ANIMAL_TO_HUMAN_GAP`, `MECHANISM_TO_TREATMENT_GAP`, `BIOMARKER_VALIDATION_GAP`, `CONTRADICTORY_EVIDENCE`, `UNDERSPECIFIED_POPULATION`, `MISSING_TEMPORAL_LINK`.

Requires Compare V2 + contradiction context.

---

### Epic E9 — Hypothesis Safety Contract (P2 design, P3 ship)

Every hypothesis carries:

```yaml
type: COMPUTATIONAL_HYPOTHESIS
generated_at: ISO8601
generated_by: pipeline_id@version
method: string
input_graph_version: string
supporting_evidence: [evidence_id]
contradictory_evidence: [evidence_id]
confidence: structured
known_gaps: [gap_id]
review_status: pending|accepted|rejected
```

Isolated from canonical claim graph.

---

## 7. Implementation waves

### Wave 1 — Reliability + Evidence UX Foundation (v2.4.0)

**Goal:** Ship Evidence Explorer; stabilize UI tests; ratchet mypy.

| Track | Owner domain | Files |
|-------|--------------|-------|
| W1-A Evidence Quality ADR + model | `biomed/` | `evidence_quality.py`, tests |
| W1-B Explorer backend completion | `web/services/`, `web/routers/` | universal_service, filters API |
| W1-C Explorer UI | `web/static/` | dashboard.js, index.html, CSS |
| W1-D Playwright stabilization | `tests/` | test_evidence_workspace_browser.py, new explorer tests |
| W1-E mypy ratchet (61→45) | adapters, routers | provenance typing pass |

**Parallelization:** W1-A blocks W1-B/C; W1-D independent; W1-E parallel.

**Validation gate:**

```bash
make ci-local
pytest tests/web/test_claim_provenance_api.py tests/test_evidence_explorer*.py -n 0
make typecheck  # ≤45 errors
```

**Release:** v2.4.0

---

### Wave 2 — Compare Product (v2.5.0)

**Goal:** Compare V2 flagship workflow with exports and Explorer drill-down.

| Track | Status | Dependencies |
|-------|--------|--------------|
| W2-A Multi-disease engine (2–5) | Complete (Sprint 1) | Wave 1 contracts |
| W2-B Dimensions + curation warnings | Complete (Sprint 1) | W2-A |
| W2-C Compare UI + export | Planned | W1-C Explorer drill-down |
| W2-D API + golden tests | Complete (Sprint 1) | W2-A |

**Validation gate:**

```bash
pytest tests/biomed/nosograph_compare/ -n 0
pytest tests/web/test_nosograph_compare_v2_api.py -n 0
# Export schema validation remains part of W2-C.
```

**Release:** v2.5.0

---

### Wave 3 — Public Demo + Interop (v2.6.0)

**Goal:** Hosted read-only demo; Phenopacket prototype; tier-gated Atlas.

| Track | Dependencies |
|-------|--------------|
| W3-A DEMO_MODE middleware | Wave 1–2 stable |
| W3-B Demo deployment docs + compose profile | W3-A |
| W3-C Atlas IA restructure (tier gating) | W1-C |
| W3-D Phenopacket export prototype | stable ClaimView |
| W3-E Python SDK (OpenAPI generator) | stable /api/v1 |

**Release:** v2.6.0

---

### Wave 4 — Knowledge Expansion

**Goal:** Source sync + literature foundation.

| Track | Contents |
|-------|----------|
| W4-A HPOA + MONDO sync | hosted dry-runs |
| W4-B ClinicalTrials.gov sync | trials Compare prep |
| W4-C Literature corpus + deterministic extraction | E6 |

**Release:** v2.7.0 (tentative)

---

### Wave 5 — Discovery

**Goal:** Contradictions, knowledge gaps, hypothesis contract (review-gated).

| Track | Contents |
|-------|----------|
| W5-A Contradiction engine | E7 |
| W5-B Knowledge gap engine | E8 |
| W5-C Hypothesis isolation + Workbench foundation | E9 |

**Release:** v3.0.0

---

## 8. Parallelization matrix

| Wave | Parallel agents | Shared contracts | Merge order |
|------|-----------------|------------------|-------------|
| 1 | 4 (A/B/C/D/E) | ADR-001 before B/C | A → B/C → merge; D anytime |
| 2 | 3 (A/B/C) | ADR-003 before C | A → B → C |
| 3 | 3 (A/B, C, D/E) | DEMO_MODE before deploy | A → B; C parallel |
| 4 | 2 (sync, literature) | SourceRef | independent |
| 5 | 2 (contradiction, gaps) | EvidenceQuality | sequential |

---

## 9. Test strategy (P2)

| Category | New tests |
|----------|-----------|
| Evidence quality serialization | unit |
| Explorer UI traceability | Playwright |
| Compare determinism | golden JSON |
| Missingness semantics | unit + API |
| Ontology normalization | import fixtures |
| Source sync | offline fixtures + hosted dry-run |
| DEMO_MODE write blocking | integration |
| Public demo smoke | Playwright against demo profile |

**Fixture improvements:**

- Multi-disease compare fixture (sle, ra, ibd)
- Contradictory evidence pair (synthetic, labeled SYNTHETIC)
- KNOWN_ABSENT vs NOT_RECORDED disease pair
- Multi-source claim (HPOA + OT) on same condition

---

## 10. Technical debt plan (bounded)

| Milestone | mypy ceiling | Playwright | Other |
|-----------|--------------|------------|-------|
| P2 start | 61 | fix Wave 1 | — |
| v2.4.0 | ≤45 | ≥90% pass | tier picker API |
| v2.5.0 | ≤25 | ≥95% pass | README citation fix |
| v3.0.0 | 0 new modules strict | required gate | package rename decision |

**Demo-blocking debt (prioritized separately):**

- UI flakes (E3)
- Broken loading states on Explorer/Compare
- 500s on `/api/v1` without biomed init (graceful empty state)
- Stale branding in satellite pages
- Unsafe write endpoints in demo mode

---

## 11. Data governance

All new sources require entry in `data/sources/registry.yaml` with:

- License SPDX
- Redistribution rights
- Attribution string
- Sync frequency
- Failure mode owner

---

## 12. External contributor strategy

| Label | Examples |
|-------|----------|
| `good first issue` | docs, test fixtures, ontology mapping fixes |
| `help wanted` | source adapter, UI Explorer polish |
| `research contribution` | L3 disease curation PRs |
| `data correction` | evidence disputes with provenance |

**First contribution paths:** disease curation (L2 PRs), source adapter tests, docs, Playwright mock extensions.

---

## 13. Community scientific review (minimal)

| Mechanism | P2 scope |
|-----------|----------|
| `review_status` on extracted claims | yes |
| Curator role in workspace reviews | exists; extend to Explorer |
| Claim dispute GitHub template | yes (docs only) |
| Institutional review board | no |

---

## 14. Public vs engineering roadmap

### Public (`ROADMAP.md`)

- **Now:** Evidence Explorer + Compare productization
- **Next:** Public demo, source sync expansion
- **Later:** Discovery (contradictions, gaps), Workbench, models

### Engineering (this document)

Full epics, waves, ADRs, acceptance gates — internal.

---

## 15. P2 P0 / P1 / P2 / P3 summary

### P0 — Must build (Wave 1–2)

| Item | Why | DoD summary |
|------|-----|-------------|
| Evidence Explorer | Brand core | Claim → evidence → source in UI |
| Compare V2 | Differentiation | 2–5 diseases, export, drill-down |
| Evidence Quality Model | Integrity | Structured dimensions, no opaque score |
| Playwright stabilization | Demo blocker | ≥90% slow Playwright pass |
| Shared contracts | Parallel safety | ADR-001/002/003 merged |

### P1 — Build immediately after (Wave 3–4)

| Item | Why |
|------|-----|
| Public read-only demo | Adoption + beta criterion |
| HPOA/MONDO sync | Claim depth |
| Literature foundation | Long-term moat |
| Phenopacket export | Research interoperability |
| Python SDK | Developer adoption |
| Reference disease L3 depth | Scientific credibility |
| Tier-gated Atlas IA | Honest UX |

### P2 — Valuable defer (Wave 4–5)

| Item | Why defer |
|------|-----------|
| Contradiction engine | Needs quality model + Explorer |
| Knowledge gaps | Needs Compare V2 |
| Mechanism causal edges | ADR + evidence burden |
| Trials depth | After CT.gov sync |
| Biomarker schema | No diagnostic model yet |
| Drug repurposing OT loop | Hypothesis labeling first |

### P3 — Long-term

| Item |
|------|
| Temporal disease model |
| Computational model registry |
| Research Workbench (full) |
| FHIR / OMOP |
| MCP server |
| Package rename + PyPI |
| NosoGraph Cloud |

---

## 16. Recommended next prompt

> **Next: launch Wave 1 — Evidence & Reliability Foundation with parallel tracks for Evidence Quality Model (ADR-001), Evidence Explorer backend + UI, Playwright stabilization, and mypy ratchet to ≤45.**

---

## References

- [Post-v2.3 assessment](../audits/post-v2.3-roadmap-assessment.md)
- [v2.3.0 release record](../audits/v2.3.0-release.md)
- [P1 post-alpha report](../audits/p1-post-alpha-report.md)
- [Evidence model](../architecture/evidence-model.md)
- [Source sync lifecycle](../architecture/source-sync-lifecycle.md)
- [Commercialization boundaries](../architecture/commercialization-boundaries.md)
