# NosoGraph Roadmap

Status key: **STABLE** | **BETA** | **EXPERIMENTAL** | **PROTOTYPE** | **PLANNED** | **NOT_IMPLEMENTED**

## Current release (v2.4.0 — Evidence Explorer)

Shipped in v2.4.0 (2026-08-22):

- [x] Evidence Explorer (claim → evidence → provenance → source workflow)
- [x] Evidence Quality Model (ADR-001 structured dimensions)
- [x] Playwright reliability fixes and hosted browser proof
- [x] Claim/evidence API enhancements (pagination, filters, related claims)

Shipped in v2.3.0 (2026-08-21):

- [x] Disease-general core (explicit disease selection, identifier resolution)
- [x] Canonical `nosograph` CLI alias (legacy `med-research` retained)
- [x] Batch strict validation and curation tiers (88/88 L2 strict-valid)
- [x] NosoGraph Compare initial vertical slice (engine + API + dashboard panel)
- [x] Claim/evidence/provenance API traceability (golden trace)
- [x] Source-sync framework + Open Targets dry-run (hosted workflow proven)
- [x] P1-0 hosted CI baseline

**Maturity:** PUBLIC_ALPHA · Registry ~10,407 scaffolds ≠ deep curation.

Internal assessment: [Post-v2.3 roadmap assessment](docs/audits/post-v2.3-roadmap-assessment.md) · Engineering plan: [P2 master plan](docs/roadmaps/p2-master-plan.md)

---

## Now (P2 Wave 1–2 — Evidence-Native Research Experience)

**Theme:** Make evidence traceability and disease comparison visible, usable, and exportable.

| Item | Target release | Status |
|------|----------------|--------|
| Evidence Explorer (claim → evidence → provenance → source) | v2.4.0 | SHIPPED_IN_V2.4.0 |
| Evidence Quality Model (structured dimensions) | v2.4.0 | SHIPPED_IN_V2.4.0 |
| Playwright / UI reliability fixes | v2.4.0 | SHIPPED_IN_V2.4.0 (hosted validated) |
| NosoGraph Compare V2 (2–5 diseases, exports, drill-down) | v2.5.0 | PLANNED |
| Tier-gated Atlas navigation | v2.5.0 | PLANNED |

---

## Next (P2 Wave 3–4)

| Item | Status |
|------|--------|
| Public read-only demo (`DEMO_MODE`, safe dataset) | PLANNED |
| Source sync expansion (HPOA, MONDO, ClinicalTrials.gov) | PLANNED |
| Phenopacket export prototype | PLANNED |
| Python SDK (OpenAPI-generated) | PLANNED |
| Literature intelligence foundation | PLANNED |
| Deep reference disease curation (L3) | PLANNED |

---

## Later (P2 Wave 5 / P3)

| Item | Status |
|------|--------|
| Contradiction engine (contextual disagreement) | PLANNED |
| Knowledge-gap engine | PLANNED |
| Research Workbench (full investigations) | PLANNED |
| Temporal disease trajectories | PLANNED |
| Computational model registry | NOT_IMPLEMENTED |
| Package rename (`med-research` → `nosograph` on PyPI) | PLANNED v3.0 |
| Official NosoGraph logo & public documentation site | IN_PROGRESS (Pages enablement may be manual) |
| GitHub Discussions Q&A | PLANNED (seed copy in docs/project/github-discussions-seed.md) |

---

## Engineering hygiene (ongoing, not the product roadmap)

| Item | Status |
|------|--------|
| mypy ratchet (61 → 45 → 25) | PLANNED |
| Automated SPDX license report in CI | PLANNED |
| PyPI publish workflow | PLANNED |

---

## Long term (P3 — not near-term)

| Item | Status |
|------|--------|
| FHIR Evidence resource export | NOT_IMPLEMENTED |
| OMOP concept mapping | NOT_IMPLEMENTED |
| Hosted SaaS / enterprise SSO | NOT_IMPLEMENTED (see [commercialization boundaries](docs/architecture/commercialization-boundaries.md)) |
| Stripe billing | NOT_IMPLEMENTED |

---

## Beta criteria (PUBLIC_ALPHA → PUBLIC_BETA)

Measurable gates before beta promotion:

- Public read-only demo live with `DEMO_MODE`
- Evidence Explorer usable on ci_validated diseases
- Compare V2 workflow with exports and explicit missingness
- Required CI green; Playwright slow suite ≥90% pass
- ≥2 source-sync hosted dry-run proofs
- Tier semantics visible on all product surfaces

---

## Disease curation expansion

Contributor-driven — not pre-complete. See [docs/disease-curation.md](docs/disease-curation.md).

Target: grow L2/L3 corpus via validated PRs, not bulk auto-promotion of scaffolds.

**v2.3.0 baseline:** 88/88 L2 modules pass strict validation; registry size (10,407) ≠ curation depth.

---

## Completed (v2.2.x – v2.3.0)

- [x] Public-readiness documentation and Apache-2.0 licensing
- [x] Honest disease tier messaging
- [x] Architecture and legal doc set
- [x] GitHub repository at `AdamEddahmouni/nosograph`
- [x] P1 core expansion (validation, compare slice, source sync, nosograph CLI)

---

## Out of scope

- Clinical decision support products
- PHI / EHR ingestion
- Full 10k scaffold manual curation
- Autonomous hypothesis publication without human review
